from locust import HttpUser, task, between
import random
import uuid
from datetime import datetime, timedelta

class ChronosTrader(HttpUser):
    wait_time = between(0.1, 0.5)
    def on_start(self):
        self.api_key = "load-test-api-key"
        self.tenant = "loadtest"
        self.headers = {"X-API-Key": self.api_key, "X-Tenant": self.tenant}
    @task(3)
    def ingest_trade(self):
        trade = {
            "id": str(uuid.uuid4()),
            "desk": "FX",
            "counterparty_id": f"CP-{random.randint(1,100)}",
            "instrument_type": "FX_SPOT",
            "currency": "NGN",
            "notional": random.randint(100000, 10000000),
            "settle_date": (datetime.utcnow()+timedelta(days=random.randint(1,30))).isoformat(),
            "idempotency_key": f"load-{uuid.uuid4().hex[:12]}"
        }
        with self.client.post("/trade/ingest_sync", json=trade, headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 200 and resp.json().get("status") in ("INGESTED","DUPLICATE"):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.json()}")
    @task(1)
    def get_risk(self):
        self.client.get("/risk/metrics", headers=self.headers)
    @task(1)
    def get_settlements(self):
        self.client.get("/nibss/settlements", headers=self.headers)
