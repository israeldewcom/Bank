import requests, json, redis, asyncio, websockets
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker

class NigeriaMarketAdapter:
    def __init__(self, redis_client=None):
        self.redis = redis_client or redis.from_url(Config.REDIS_URL)
        self.cb = CircuitBreaker("CBN_API", 3, 30)
        self.session = requests.Session()
        self.session.timeout = 10
        self.ws_connected = False
        self._ws_task = None

    async def connect_ngx_websocket(self):
        try:
            self.ws = await websockets.connect(Config.NGX_WEBSOCKET)
            self.ws_connected = True
            logger.info("Connected to NGX WebSocket")
            asyncio.create_task(self._ws_listener())
        except Exception as e:
            logger.error(f"NGX WebSocket failed: {e}")

    async def _ws_listener(self):
        async for message in self.ws:
            try:
                data = json.loads(message)
                if 'symbol' in data and 'price' in data:
                    self.redis.setex(f"ngx:{data['symbol']}", 60, data['price'])
            except Exception as e:
                logger.error(f"WS parse error: {e}")

    @property
    def cbn_mpr(self) -> float:
        cache_key = "ng:cbn:mpr"
        cached = self.redis.get(cache_key)
        if cached:
            return float(cached)
        try:
            resp = self.session.get(f"{Config.CBN_OPENAPI_URL}/mpr")
            resp.raise_for_status()
            data = resp.json()
            rate = float(data.get("rate", 26.75)) / 100.0
        except Exception as e:
            logger.warning(f"CBN MPR fetch failed: {e}, using default")
            rate = 0.2675
        self.redis.setex(cache_key, 3600, rate)
        return rate

    @property
    def ngx_all_share(self) -> float:
        cache_key = "ng:ngx:asi"
        cached = self.redis.get(cache_key)
        if cached:
            return float(cached)
        try:
            if Config.MARKET_DATA_PROVIDER == "bloomberg" and Config.BLOOMBERG_API_KEY:
                resp = self.session.get(f"{Config.BLOOMBERG_API_URL}/indices/NGXASI", headers={"Authorization": Config.BLOOMBERG_API_KEY})
                resp.raise_for_status()
                data = resp.json()
                value = float(data['value'])
            else:
                resp = self.session.get(f"{Config.NGX_API_URL}/indices/allshare")
                resp.raise_for_status()
                data = resp.json()
                value = float(data.get("value", 98000))
        except Exception as e:
            logger.warning(f"NGX fetch failed: {e}, using default")
            value = 98000.0
        self.redis.setex(cache_key, 300, value)
        return value

    @property
    def ngn_usd_parallel(self) -> float:
        cache_key = "ng:ngn_usd_parallel"
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

nigeria = NigeriaMarketAdapter()
