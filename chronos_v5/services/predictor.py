# services package
import joblib, numpy as np, pandas as pd, redis, asyncio
from river import linear_model, preprocessing, compose
from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal, async_database, AsyncSessionLocal
from chronos_v5.logger_setup import logger
from chronos_v5.drift_detector import DriftDetector
from chronos_v5.models import Trade, FailHistory, PnLAttribution, Counterparty
from chronos_v5.hsm_abstraction import hsm
from datetime import datetime, timezone

class SettlementPredictor:
    def __init__(self, db_session=None, retrain_on_init=True):
        self.db = db_session or SyncSessionLocal()
        self.model = None
        self.online_model = None
        self.drift_detector = DriftDetector()
        self.feature_store = {}
        self._load_model()
        if retrain_on_init:
            self._retrain_if_needed()

    def _load_model(self):
        try:
            self.model = joblib.load(Config.MODEL_PATH)
            logger.info("Loaded XGBoost model")
        except:
            logger.warning("No model found, initializing fresh")
            from sklearn.ensemble import GradientBoostingClassifier
            self.model = GradientBoostingClassifier(n_estimators=100)
        self.online_model = compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LogisticRegression()
        )

    def _retrain_if_needed(self):
        try:
            import pandas as pd
            query = "SELECT * FROM fail_history WHERE timestamp > NOW() - INTERVAL '30 days'"
            df = pd.read_sql(query, self.db.bind)
            if len(df) > 100:
                features = self._generate_features(df)
                targets = df['failed'].values
                self.model.fit(features, targets)
                joblib.dump(self.model, Config.MODEL_PATH)
                logger.info("Model retrained on recent data")
        except Exception as e:
            logger.error(f"Retrain failed: {e}")

    def _generate_features(self, trade_dict_or_df):
        if isinstance(trade_dict_or_df, dict):
            d = trade_dict_or_df
            features = {
                'notional': d.get('notional', 0),
                'counterparty_risk': self._get_counterparty_risk(d.get('counterparty_id')),
                'days_to_settle': (datetime.fromisoformat(d['settle_date']) - datetime.now()).days,
                'instrument_volatility': 0.05,
                'market_volatility': 0.1,
                'haircut': 0.02,
                'rehypo_yield': Config.REHYPOTHECATION_YIELD,
                'emergency_rate': Config.EMERGENCY_BORROW_RATE,
                'desk_exposure': self._get_desk_exposure(d.get('desk')),
            }
            return pd.DataFrame([features])
        else:
            df = trade_dict_or_df.copy()
            df['days_to_settle'] = (pd.to_datetime(df['settle_date']) - pd.Timestamp.now()).dt.days
            df['counterparty_risk'] = df['counterparty_id'].apply(self._get_counterparty_risk)
            df['desk_exposure'] = df['desk'].apply(self._get_desk_exposure)
            return df[['notional','counterparty_risk','days_to_settle','instrument_volatility','market_volatility','haircut','rehypo_yield','emergency_rate','desk_exposure']]

    def _get_counterparty_risk(self, cid):
        if cid:
            cp = self.db.query(Counterparty).filter(Counterparty.id == cid).first()
            if cp:
                return cp.risk_score
        return 0.1

    def _get_desk_exposure(self, desk):
        from chronos_v5.repositories.desk_exposure_repository import DeskExposureRepository
        repo = DeskExposureRepository()
        return repo.get_desk_exposure(desk) / 1e9

    def predict(self, trade_dict: dict) -> float:
        X = self._generate_features(trade_dict)
        prob = self.model.predict_proba(X)[0][1]
        self.online_model.learn_one(X.iloc[0].to_dict(), prob > 0.15)
        self.drift_detector.update(prob)
        if self.drift_detector.drift_detected:
            logger.warning("Concept drift detected! Triggering retrain.")
            self._retrain_if_needed()
        return prob

    async def predict_async(self, trade_dict: dict) -> float:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.predict, trade_dict)

    async def predict_and_store_async(self, trade_dict: dict) -> float:
        prob = await self.predict_async(trade_dict)
        r = redis.from_url(Config.REDIS_URL)
        r.setex(f"pred:{trade_dict['id']}", 300, prob)
        if Config.HSM_ENABLED:
            encrypted = hsm.encrypt(trade_dict.get('counterparty_id', '').encode())
        return prob

    async def online_update(self, trade_dict, actual_fail):
        X = self._generate_features(trade_dict)
        self.online_model.learn_one(X.iloc[0].to_dict(), actual_fail)
        if datetime.now().minute % 5 == 0:
            joblib.dump(self.online_model, Config.MODEL_BACKUP_PATH)
            logger.info("Online model persisted")
