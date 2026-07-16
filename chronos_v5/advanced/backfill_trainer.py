import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.services.predictor import SettlementPredictor
from chronos_v5.advanced.advanced_config import AdvancedConfig

class BackfillTrainer:
    def __init__(self):
        self.csv_path = AdvancedConfig.BACKFILL_CSV_PATH
        self.model_path = AdvancedConfig.BACKFILL_MODEL_OUTPUT
        self.predictor = SettlementPredictor(retrain_on_init=False)

    def train(self):
        if not AdvancedConfig.BACKFILL_TRAINING_ENABLED:
            logger.info("Backfill training disabled")
            return
        try:
            df = pd.read_csv(self.csv_path)
            logger.info(f"Loaded {len(df)} historical records from {self.csv_path}")
            required_cols = ['notional', 'counterparty_id', 'settle_date', 'desk', 'failed']
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")
            features = self.predictor._generate_features(df)
            targets = df['failed'].values
            model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.1, max_depth=5)
            model.fit(features, targets)
            joblib.dump(model, self.model_path)
            logger.info(f"Model trained on {len(df)} records and saved to {self.model_path}")
            self.predictor.model = model
            return True
        except Exception as e:
            logger.error(f"Backfill training failed: {e}")
            return False
