import pandas as pd
import numpy as np
from chronos_v5.config import Config
from chronos_v5.services.predictor import SettlementPredictor
from chronos_v5.pricing_engine import PricingEngine
from chronos_v5.risk_engine import RiskEngine
from chronos_v5.logger_setup import logger

class BacktestEngine:
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.predictor = SettlementPredictor(retrain_on_init=False)
        self.pricing = PricingEngine()

    def run(self, trade_col="trades"):
        results = []
        for idx, row in self.data.iterrows():
            trade_dict = row.to_dict()
            prob = self.predictor.predict(trade_dict)
            # Use actual fail if available, else simulate based on prob
            if 'failed' in trade_dict:
                actual_fail = trade_dict['failed']
            else:
                actual_fail = np.random.rand() < prob
            price = self.pricing.get_client_price(trade_dict['counterparty_id'], trade_dict.get('instrument_type', 'UNKNOWN'), trade_dict['notional'])
            results.append({
                'trade_id': trade_dict.get('id', idx),
                'predicted_fail_prob': prob,
                'actual_fail': actual_fail,
                'price': price,
                'saved': trade_dict['notional'] * Config.REHYPOTHECATION_YIELD if not actual_fail else 0
            })
        return pd.DataFrame(results)
