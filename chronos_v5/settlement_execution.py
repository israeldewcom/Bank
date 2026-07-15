import requests, json, time
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker

class SettlementExecution:
    def __init__(self):
        self.enabled = Config.EXECUTION_ENGINE_ENABLED
        self.fix_url = Config.FIX_ENGINE_URL
        self.sender_comp = Config.FIX_SENDER_COMP_ID
        self.target_comp = Config.FIX_TARGET_COMP_ID
        self.api_key = Config.EXECUTION_GATEWAY_API_KEY
        self.max_retries = Config.EXECUTION_MAX_RETRIES
        self.retry_delay = Config.EXECUTION_RETRY_DELAY
        self.cb = CircuitBreaker("Execution", 3, 30)

    def send_order(self, trade_id: str, side: str, quantity: float, price: float, order_type="LIMIT"):
        if not self.enabled:
            logger.info(f"Execution disabled, would send order {trade_id}")
            return {"status": "SIMULATED"}
        @self.cb
        def _send():
            payload = {
                "ClOrdID": trade_id,
                "Side": side,
                "OrderQty": quantity,
                "Price": price,
                "OrdType": order_type,
                "SenderCompID": self.sender_comp,
                "TargetCompID": self.target_comp
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}
            for attempt in range(self.max_retries):
                try:
                    resp = requests.post(f"{self.fix_url}/order", json=payload, headers=headers, timeout=10)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    logger.warning(f"Execution attempt {attempt+1} failed: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    else:
                        raise
        return _send()
