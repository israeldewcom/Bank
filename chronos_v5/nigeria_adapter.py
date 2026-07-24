# chronos_v5/nigeria_adapter.py
import requests, json, redis, asyncio, websockets
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker
from chronos_v5.services.tenant_config_service import TenantConfigService

class NigeriaMarketAdapter:
    def __init__(self, tenant: str = "default", redis_client=None):
        self.tenant = tenant
        self.redis = redis_client or redis.from_url(Config.REDIS_URL)
        self.tenant_service = TenantConfigService()
        self.cb = CircuitBreaker("CBN_API", 3, 30)
        self.session = requests.Session()
        self.session.timeout = 10
        self.ws_connected = False
        self._ws_task = None

    def _tenant_key(self, key: str) -> str:
        return f"{self.tenant}:{key}"

    async def connect_ngx_websocket(self):
        try:
            self.ws = await websockets.connect(Config.NGX_WEBSOCKET)
            self.ws_connected = True
            logger.info(f"Connected to NGX WebSocket for tenant {self.tenant}")
            asyncio.create_task(self._ws_listener())
        except Exception as e:
            logger.error(f"NGX WebSocket failed for tenant {self.tenant}: {e}")

    async def _ws_listener(self):
        async for message in self.ws:
            try:
                data = json.loads(message)
                if 'symbol' in data and 'price' in data:
                    self.redis.setex(self._tenant_key(f"ngx:{data['symbol']}"), 60, data['price'])
            except Exception as e:
                logger.error(f"WS parse error: {e}")

    @property
    def cbn_mpr(self) -> float:
        cache_key = self._tenant_key("ng:cbn:mpr")
        cached = self.redis.get(cache_key)
        if cached:
            return float(cached)
        tenant_config = self.tenant_service.get_config(self.tenant)
        cbn_url = tenant_config.get("cbn_openapi_url", Config.CBN_OPENAPI_URL)
        try:
            resp = self.session.get(f"{cbn_url}/mpr")
            resp.raise_for_status()
            data = resp.json()
            rate = float(data.get("rate", 26.75)) / 100.0
        except Exception as e:
            logger.warning(f"CBN MPR fetch failed for tenant {self.tenant}: {e}, using default")
            rate = 0.2675
        self.redis.setex(cache_key, 3600, rate)
        return rate

    @property
    def ngx_all_share(self) -> float:
        cache_key = self._tenant_key("ng:ngx:asi")
        cached = self.redis.get(cache_key)
        if cached:
            return float(cached)
        tenant_config = self.tenant_service.get_config(self.tenant)
        bloomberg_key = tenant_config.get("bloomberg_api_key", Config.BLOOMBERG_API_KEY)
        try:
            if Config.MARKET_DATA_PROVIDER == "bloomberg" and bloomberg_key:
                resp = self.session.get(f"{Config.BLOOMBERG_API_URL}/indices/NGXASI", headers={"Authorization": bloomberg_key})
                resp.raise_for_status()
                data = resp.json()
                value = float(data['value'])
            else:
                ngx_url = tenant_config.get("ngx_api_url", Config.NGX_API_URL)
                resp = self.session.get(f"{ngx_url}/indices/allshare")
                resp.raise_for_status()
                data = resp.json()
                value = float(data.get("value", 98000))
        except Exception as e:
            logger.warning(f"NGX fetch failed for tenant {self.tenant}: {e}, using default")
            value = 98000.0
        self.redis.setex(cache_key, 300, value)
        return value

    @property
    def ngn_usd_parallel(self) -> float:
        cache_key = self._tenant_key("ng:ngn_usd_parallel")
        cached = self.redis.get(cache_key)
        if cached:
            return float(cached)
        try:
            resp = self.session.get("https://api.abokifx.com/rates")
            resp.raise_for_status()
            data = resp.json()
            rate = float(data['usd']['ngn'])
        except:
            rate = 1500.0 + (datetime.now().minute % 100)
        self.redis.setex(cache_key, 60, rate)
        return rate

    def get_asset_volatility(self, asset_type: str) -> float:
        base = {
            "NGX_EQUITY": 0.12,
            "TBILL": 0.03,
            "CORP_BOND": 0.06,
            "NGN": 0.04,
            "CASH": 0.01
        }.get(asset_type, 0.08)
        mpr = self.cbn_mpr
        vol = base * (1 + mpr * 0.5)
        return min(0.50, vol)

# Default instance (global) – used by existing code
nigeria = NigeriaMarketAdapter()
