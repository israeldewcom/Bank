# chronos_v5/nibss_client.py
import requests
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker
from chronos_v5.services.tenant_config_service import TenantConfigService

class NIBSSClient:
    def __init__(self, tenant: str = "default"):
        self.tenant = tenant
        self.tenant_service = TenantConfigService()
        self.cb = CircuitBreaker("NIBSS", 5, 60)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _get_tenant_config(self):
        config = self.tenant_service.get_config(self.tenant)
        api_key = config.get("nibss_api_key")
        if not api_key or api_key == "********":
            api_key = Config.NIBSS_API_KEY
        api_url = config.get("cbn_openapi_url") or Config.NIBSS_API_URL
        return api_url, api_key

    def submit_settlement(self, trade_id: str, amount: float, counterparty_bvn: str, collateral_ref: str = None):
        @self.cb
        def _call():
            api_url, api_key = self._get_tenant_config()
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "tradeId": trade_id, "amount": amount, "bvn": counterparty_bvn,
                "collateralRef": collateral_ref, "timestamp": datetime.now(timezone.utc).isoformat()
            }
            resp = self.session.post(f"{api_url}/settle", json=payload, headers=headers, timeout=Config.NIBSS_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        try:
            return _call()
        except Exception as e:
            logger.error(f"NIBSS settle failed for tenant {self.tenant}: {e}")
            return {"status": "FAILED", "code": "NIBSS-ERR", "message": str(e)}

    def recall_collateral(self, order_ref: str):
        @self.cb
        def _call():
            api_url, api_key = self._get_tenant_config()
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            resp = self.session.post(f"{api_url}/recall", json={"ref": order_ref}, headers=headers, timeout=Config.NIBSS_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        try:
            return _call()
        except Exception as e:
            logger.error(f"NIBSS recall failed for tenant {self.tenant}: {e}")
            return {"status": "ERROR"}
