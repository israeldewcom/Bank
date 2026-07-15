import requests, uuid, json
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker

class NIBSSClient:
    def __init__(self):
        self.api_url = Config.NIBSS_API_URL
        self.api_key = Config.NIBSS_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        self.cb = CircuitBreaker("NIBSS", 5, 60)

    def submit_settlement(self, trade_id: str, amount: float, counterparty_bvn: str, collateral_ref: str = None):
        @self.cb
        def _call():
            payload = {
                "tradeId": trade_id,
                "amount": amount,
                "bvn": counterparty_bvn,
                "collateralRef": collateral_ref,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            resp = self.session.post(f"{self.api_url}/settle", json=payload, timeout=Config.NIBSS_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        try:
            return _call()
        except Exception as e:
            logger.error(f"NIBSS settle failed: {e}")
            return {"status": "FAILED", "code": "NIBSS-ERR", "message": str(e)}

    def recall_collateral(self, order_ref: str):
        @self.cb
        def _call():
            resp = self.session.post(f"{self.api_url}/recall", json={"ref": order_ref})
            resp.raise_for_status()
            return resp.json()
        try:
            return _call()
        except Exception as e:
            logger.error(f"NIBSS recall failed: {e}")
            return {"status": "ERROR"}

nibss_client = NIBSSClient()
