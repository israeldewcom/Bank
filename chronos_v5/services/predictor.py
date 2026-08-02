# chronos_v5/services/predictor.py
import joblib
import numpy as np
import pandas as pd
import redis
import asyncio
from river import linear_model, preprocessing, compose
from chronos_v5.config import Config
from chronos_v5.database import SyncSessionLocal
from chronos_v5.logger_setup import logger
from chronos_v5.drift_detector import DriftDetector
from chronos_v5.models import Trade, FailHistory, PnLAttribution, Counterparty
from chronos_v5.hsm_abstraction import hsm
from datetime import datetime, timezone, timedelta
from sklearn.exceptions import NotFittedError
from sqlalchemy import text

class _ConstantProbabilityPredictor:
    """A dummy predictor that always returns a constant probability."""
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, X):
        n = len(X) if hasattr(X, '__len__') else 1
        return np.array([[1 - self.probability, self.probability]] * n)

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
        self._ensure_model_fitted()

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

    def _ensure_model_fitted(self):
        try:
            dummy = pd.DataFrame([[0]*9], columns=[
                'notional', 'counterparty_risk', 'days_to_settle',
                'instrument_volatility', 'market_volatility',
                'haircut', 'rehypo_yield', 'emergency_rate', 'desk_exposure'
            ])
            self.model.predict_proba(dummy)
        except NotFittedError:
            logger.warning("Model not fitted – training on historical baseline.")
            self._fit_historical_baseline()
        except Exception as e:
            logger.error(f"Model check failed: {e}")
            self._fit_historical_baseline()

    def _fit_historical_baseline(self):
        from sklearn.dummy import DummyClassifier
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            history = self.db.query(FailHistory).filter(
                FailHistory.timestamp > cutoff
            ).limit(1000).all()
            if history:
                fail_count = sum(1 for h in history if h.failed)
                total = len(history)
                fail_rate = fail_count / total if total > 0 else Config.DEFAULT_FAIL_RATE
                logger.info(f"Historical baseline fitted: {fail_rate:.4f} fail rate from {total} records")
            else:
                fail_rate = Config.DEFAULT_FAIL_RATE
                logger.warning(f"No historical data found. Using default fail rate: {fail_rate:.4f}")

            n_samples = 1000
            n_fail = int(n_samples * fail_rate)
            n_success = n_samples - n_fail
            X = np.random.randn(n_samples, 9)
            y = np.array([1] * n_fail + [0] * n_success)
            idx = np.random.permutation(n_samples)
            X, y = X[idx], y[idx]
            self.model = DummyClassifier(strategy="prior")
            self.model.fit(X, y)
            logger.info(f"Baseline model fitted with prior fail rate: {fail_rate:.4f}")
        except Exception as e:
            logger.error(f"Historical baseline fitting failed: {e}. Falling back to constant predictor.")
            self.model = _ConstantProbabilityPredictor(Config.DEFAULT_FAIL_RATE)
            logger.info(f"Constant probability predictor set to {Config.DEFAULT_FAIL_RATE:.4f}")

    def _retrain_if_needed(self):
        try:
            # Query directly from Trade table to get needed columns, including tenant
            query = text("""
                SELECT t.id, t.desk, t.counterparty_id, t.notional, t.settle_date,
                       t.instrument_type, t.tenant, t.created_at,
                       fh.failed
                FROM trades t
                LEFT JOIN fail_history fh ON t.id = fh.trade_id
                WHERE t.created_at > NOW() - INTERVAL '30 days'
                  AND fh.failed IS NOT NULL
            """)
            df = pd.read_sql(query, self.db.bind)
            if len(df) > 100:
                features = self._generate_features(df)
                targets = df['failed'].values
                self.model.fit(features, targets)
                joblib.dump(self.model, Config.MODEL_PATH)
                logger.info("Model retrained on recent data from Trade join")
            else:
                logger.info("Not enough data for retraining")
        except Exception as e:
            logger.error(f"Retrain failed: {e}")

    def _generate_features(self, trade_dict_or_df):
        if isinstance(trade_dict_or_df, dict):
            d = trade_dict_or_df
            tenant = d.get('tenant')
            settle_dt = datetime.fromisoformat(d['settle_date']).replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            days_to_settle = (settle_dt - now_utc).days
            features = {
                'notional': d.get('notional', 0),
                'counterparty_risk': self._get_counterparty_risk(d.get('counterparty_id'), tenant),
                'days_to_settle': days_to_settle,
                'instrument_volatility': 0.05,
                'market_volatility': 0.1,
                'haircut': 0.02,
                'rehypo_yield': Config.REHYPOTHECATION_YIELD,
                'emergency_rate': Config.EMERGENCY_BORROW_RATE,
                'desk_exposure': self._get_desk_exposure(d.get('desk'), tenant),
            }
            return pd.DataFrame([features])
        else:
            df = trade_dict_or_df.copy()
            df['settle_date'] = pd.to_datetime(df['settle_date'])
            if df['settle_date'].dt.tz is None:
                df['settle_date'] = df['settle_date'].dt.tz_localize('utc')
            now_utc = datetime.now(timezone.utc)
            df['days_to_settle'] = (df['settle_date'] - now_utc).dt.days
            tenant_col = df['tenant'] if 'tenant' in df.columns else pd.Series([None] * len(df))
            df['counterparty_risk'] = [
                self._get_counterparty_risk(cid, t) for cid, t in zip(df['counterparty_id'], tenant_col)
            ]
            df['desk_exposure'] = [
                self._get_desk_exposure(desk, t) for desk, t in zip(df['desk'], tenant_col)
            ]
            return df[['notional','counterparty_risk','days_to_settle','instrument_volatility','market_volatility','haircut','rehypo_yield','emergency_rate','desk_exposure']]

    def _get_counterparty_risk(self, cid, tenant):
        if not cid:
            return 0.1
        if not tenant:
            logger.error(f"_get_counterparty_risk called without a tenant for cid={cid}; "
                          f"refusing to run an unscoped lookup, returning neutral default")
            return 0.1
        db = SyncSessionLocal()
        try:
            q = db.query(Counterparty).filter(Counterparty.id == cid, Counterparty.tenant == tenant)
            cp = q.first()
            if cp:
                return cp.risk_score
        except Exception as e:
            logger.error(f"Counterparty risk fetch failed: {e}")
            db.rollback()
        finally:
            db.close()
        return 0.1

    def _get_desk_exposure(self, desk, tenant):
        if not tenant:
            logger.error(f"_get_desk_exposure called without a tenant for desk={desk}; "
                          f"refusing to run an unscoped lookup, returning 0.0 (this "
                          f"understates risk — check the caller)")
            return 0.0
        try:
            from chronos_v5.repositories.desk_exposure_repository import DeskExposureRepository
            repo = DeskExposureRepository()
            return repo.get_desk_exposure(desk, tenant=tenant) / 1e9
        except Exception as e:
            logger.error(f"Desk exposure fetch failed: {e}")
            return 0.0

    def predict(self, trade_dict: dict) -> float:
        X = self._generate_features(trade_dict)
        self._ensure_model_fitted()
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
