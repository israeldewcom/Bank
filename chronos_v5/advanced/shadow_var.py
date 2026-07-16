import numpy as np
import pandas as pd
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade, RiskMetrics
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.advanced.advanced_config import AdvancedConfig
from datetime import datetime, timedelta
import redis
import json

class ShadowVaR:
    def __init__(self):
        self.db = SyncSessionLocal()
        self.redis = redis.from_url(Config.REDIS_URL)
        self.last_update = None

    def compute_shadow_var(self, desk=None):
        cutoff = datetime.now() - timedelta(days=AdvancedConfig.SHADOW_VAR_LOOKBACK_DAYS)
        query = self.db.query(Trade).filter(Trade.created_at > cutoff)
        if desk:
            query = query.filter(Trade.desk == desk)
        trades = query.all()
        if not trades:
            return None
        mkt_vol = self.redis.get("market:volatility")
        if mkt_vol:
            vol_base = float(mkt_vol)
        else:
            vol_base = 0.02
        returns = []
        for t in trades:
            vol = vol_base * (1.0 + 0.5 * (t.notional / 1e9))
            daily_pnl = t.notional * np.random.normal(0, vol, 252)
            returns.extend(daily_pnl.tolist())
        if not returns:
            return None
        returns = np.array(returns)
        var_99 = np.percentile(returns, 1)
        var_95 = np.percentile(returns, 5)
        es_99 = returns[returns <= var_99].mean() if any(returns <= var_99) else var_99
        stress_shocks = {
            '2008': -0.4,
            'COVID': -0.3,
            'NIGERIA_2020': -0.25,
            'CURRENT_VOL': -vol_base * 10
        }
        stress_losses = {}
        for name, shock in stress_shocks.items():
            stress_losses[name] = np.mean(returns) * (1 + shock)
        data = {
            "var_99": float(var_99),
            "var_95": float(var_95),
            "es_99": float(es_99),
            "stress_losses": stress_losses,
            "timestamp": datetime.now().isoformat()
        }
        key = f"shadow_var:{desk or 'TOTAL'}"
        self.redis.setex(key, 600, json.dumps(data))
        logger.info(f"Shadow VaR computed for {desk or 'TOTAL'}")
        return data

    def get_shadow_var(self, desk=None):
        key = f"shadow_var:{desk or 'TOTAL'}"
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)
        return self.compute_shadow_var(desk)

    def run_continuous(self):
        import schedule, time
        def job():
            self.compute_shadow_var()
            desks = set([t.desk for t in self.db.query(Trade.desk).distinct()])
            for d in desks:
                self.compute_shadow_var(d)
        schedule.every(AdvancedConfig.SHADOW_VAR_UPDATE_INTERVAL_SEC).seconds.do(job)
        while True:
            schedule.run_pending()
            time.sleep(1)
