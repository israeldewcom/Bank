# chronos_v5/nibss_client.py
# RELIABILITY FIX: submit_settlement previously made a single POST with no
# idempotency key and no retry — a dropped response (timeout, connection
# reset) was indistinguishable from a dropped request, and retrying at any
# layer above this client would double-submit the settlement at NIBSS. This
# now follows the same pattern already proven correct in
# settlement_execution.py: (1) atomically reserve the settlement intent on
# the Trade row itself via a guarded status transition before any network
# call, so concurrent/duplicate callers get a DUPLICATE result instead of a
# second network call; (2) send a stable idempotency key (the trade_id) as
# part of the payload so NIBSS's own side can dedupe if the client retries;
# (3) retry with backoff, reusing the same request each attempt rather than
# minting a new one.
import time
from datetime import datetime, timezone

import requests
from sqlalchemy import and_

from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker
from chronos_v5.services.tenant_config_service import TenantConfigService
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade


class DuplicateSettlementError(Exception):
    """Raised when a settlement has already been reserved/sent for this trade."""
    pass


class NIBSSClient:
    def __init__(self, tenant: str = "default"):
        self.tenant = tenant
        self.tenant_service = TenantConfigService()
        self.cb = CircuitBreaker("NIBSS", 5, 60)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.max_retries = Config.NIBSS_MAX_RETRIES
        self.retry_delay = Config.NIBSS_RETRY_DELAY

    def _get_tenant_config(self):
        config = self.tenant_service.get_config(self.tenant)
        api_key = config.get("nibss_api_key")
        if not api_key or api_key == "********":
            api_key = Config.NIBSS_API_KEY
        api_url = config.get("cbn_openapi_url") or Config.NIBSS_API_URL
        return api_url, api_key

    def _reserve_settlement(self, trade_id: str):
        """
        Atomically transition PENDING -> SETTLING for this tenant's trade.
        The WHERE clause (id, tenant, status == PENDING) is the source of
        truth for idempotency: if another call already moved the row out of
        PENDING, this UPDATE affects zero rows and we know a settlement
        attempt is already in flight or done, without ever making a second
        network call.
        """
        db = SyncSessionLocal()
        try:
            result = db.execute(
                Trade.__table__.update()
                .where(and_(
                    Trade.id == trade_id,
                    Trade.tenant == self.tenant,
                    Trade.status == "PENDING",
                ))
                .values(status="SETTLING")
            )
            db.commit()
            if result.rowcount == 0:
                existing = db.query(Trade).filter(
                    Trade.id == trade_id, Trade.tenant == self.tenant
                ).first()
                raise DuplicateSettlementError(
                    existing.status if existing else "UNKNOWN"
                )
        finally:
            db.close()

    def _finalize_settlement(self, trade_id: str, status: str, nibss_ref: str = None):
        db = SyncSessionLocal()
        try:
            trade = db.query(Trade).filter(
                Trade.id == trade_id, Trade.tenant == self.tenant
            ).first()
            if trade:
                trade.status = status
                if nibss_ref:
                    trade.nibss_ref = nibss_ref
                if status == "SETTLED":
                    trade.settled_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to finalize settlement status for trade {trade_id}: {e}")
        finally:
            db.close()

    def submit_settlement(self, trade_id: str, amount: float, counterparty_bvn: str, collateral_ref: str = None):
        try:
            self._reserve_settlement(trade_id)
        except DuplicateSettlementError as e:
            logger.info(f"Settlement already reserved/sent for trade {trade_id} (status={e})")
            return {"status": "DUPLICATE", "trade_id": trade_id, "existing_status": str(e)}

        @self.cb
        def _call():
            api_url, api_key = self._get_tenant_config()
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "tradeId": trade_id,
                "idempotencyKey": trade_id,
                "amount": amount,
                "bvn": counterparty_bvn,
                "collateralRef": collateral_ref,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            last_exc = None
            for attempt in range(self.max_retries):
                try:
                    resp = self.session.post(
                        f"{api_url}/settle", json=payload, headers=headers, timeout=Config.NIBSS_TIMEOUT
                    )
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_exc = e
                    logger.warning(f"NIBSS settle attempt {attempt + 1} failed for trade {trade_id}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            raise last_exc

        try:
            result = _call()
            nibss_ref = result.get("reference") if isinstance(result, dict) else None
            self._finalize_settlement(trade_id, status="SETTLED", nibss_ref=nibss_ref)
            return result
        except Exception as e:
            logger.error(f"NIBSS settle failed for tenant {self.tenant}, trade {trade_id}: {e}")
            self._finalize_settlement(trade_id, status="SETTLEMENT_FAILED")
            return {"status": "FAILED", "code": "NIBSS-ERR", "message": str(e)}

    def recall_collateral(self, order_ref: str):
        @self.cb
        def _call():
            api_url, api_key = self._get_tenant_config()
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"ref": order_ref, "idempotencyKey": order_ref}
            last_exc = None
            for attempt in range(self.max_retries):
                try:
                    resp = self.session.post(
                        f"{api_url}/recall", json=payload, headers=headers, timeout=Config.NIBSS_TIMEOUT
                    )
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_exc = e
                    logger.warning(f"NIBSS recall attempt {attempt + 1} failed for ref {order_ref}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            raise last_exc

        try:
            return _call()
        except Exception as e:
            logger.error(f"NIBSS recall failed for tenant {self.tenant}: {e}")
            return {"status": "ERROR", "message": str(e)}
