# chronos_v5/market_data.py
import requests, redis, asyncio
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.nigeria_adapter import nigeria
from datetime import datetime, timedelta
from chronos_v5.services.tenant_config_service import TenantConfigService

class MarketDataAggregator:
    def __init__(self, tenant: str = "default"):
        self.tenant = tenant
        self.redis = redis.from_url(Config.REDIS_URL)
        self.tenant_service = TenantConfigService()

    def _get_tenant_key(self, key: str) -> str:
        return f"{self.tenant}:{key}"

    def get_price(self, symbol: str) -> float:
        cached = self.redis.get(self._get_tenant_key(f"price:{symbol}"))
        if cached:
            return float(cached)
        price = self._fetch_from_provider(symbol)
        self.redis.setex(self._get_tenant_key(f"price:{symbol}"), 60, price)
        return price

    def _fetch_from_provider(self, symbol: str):
        # Get tenant-specific config
        tenant_config = self.tenant_service.get_config(self.tenant)
        bloomberg_key = tenant_config.get("bloomberg_api_key", Config.BLOOMBERG_API_KEY)
        reuters_key = tenant_config.get("reuters_api_key", Config.REUTERS_API_KEY)
        alpha_key = tenant_config.get("alpha_vantage_key", Config.ALPHA_VANTAGE_API_KEY)

        if Config.MARKET_DATA_PROVIDER == "bloomberg" and bloomberg_key:
            try:
                resp = requests.get(f"{Config.BLOOMBERG_API_URL}/securities/{symbol}/price",
                                    headers={"Authorization": bloomberg_key},
                                    timeout=Config.MARKET_DATA_TIMEOUT)
                resp.raise_for_status()
                return float(resp.json()['price'])
            except Exception as e:
                logger.warning(f"Bloomberg fetch failed for {symbol}: {e}")
        elif Config.MARKET_DATA_PROVIDER == "reuters" and reuters_key:
            try:
                resp = requests.get(f"{Config.REUTERS_API_URL}/prices/{symbol}",
                                    headers={"Authorization": f"Bearer {reuters_key}"},
                                    timeout=Config.MARKET_DATA_TIMEOUT)
                resp.raise_for_status()
                return float(resp.json()['price'])
            except Exception as e:
                logger.warning(f"Reuters fetch failed for {symbol}: {e}")
        if alpha_key:
            try:
                resp = requests.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={alpha_key}",
                                    timeout=Config.MARKET_DATA_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                return float(data['Global Quote']['05. price'])
            except Exception as e:
                logger.warning(f"Alpha Vantage fetch failed: {e}")
        try:
            resp = requests.get(f"{Config.NGX_API_URL}/prices/{symbol}", timeout=Config.MARKET_DATA_TIMEOUT)
            resp.raise_for_status()
            return float(resp.json()['price'])
        except:
            logger.error(f"All market data sources failed for {symbol}, using default 100.0")
            return 100.0

    def compute_alpha(self) -> dict:
        signals = {}
        if Config.ALPHA_STRATEGY_TYPE == "mean_reversion":
            for asset in Config.ALPHA_STRATEGY_ASSETS:
                price = self.get_price(asset)
                ma = self._get_moving_average(asset)
                if price > ma * 1.02:
                    signals[asset] = -1.0
                elif price < ma * 0.98:
                    signals[asset] = 1.0
                else:
                    signals[asset] = 0.0
        elif Config.ALPHA_STRATEGY_TYPE == "momentum":
            for asset in Config.ALPHA_STRATEGY_ASSETS:
                price = self.get_price(asset)
                old_price = self.redis.get(self._get_tenant_key(f"price_old:{asset}"))
                if old_price:
                    change = (price - float(old_price)) / float(old_price)
                    signals[asset] = change
                else:
                    signals[asset] = 0.0
                self.redis.setex(self._get_tenant_key(f"price_old:{asset}"), 600, price)
        for asset, value in signals.items():
            self.redis.setex(self._get_tenant_key(f"alpha:{asset}"), 60, value)
        return signals

    def _get_moving_average(self, asset, days=30):
        try:
            from chronos_v5.database import SyncSessionLocal
            from chronos_v5.models import MarketDataPoint
            db = SyncSessionLocal()
            cutoff = datetime.utcnow() - timedelta(days=days)
            points = db.query(MarketDataPoint).filter(
                MarketDataPoint.symbol == asset,
                MarketDataPoint.timestamp > cutoff
            ).order_by(MarketDataPoint.timestamp).all()
            db.close()
            if points:
                avg = sum(p.price for p in points) / len(points)
                return avg
        except:
            pass
        return 100.0
