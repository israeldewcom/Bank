import asyncio
import time
import uuid

import requests
from sqlalchemy.exc import IntegrityError

from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.circuit_breaker import CircuitBreaker
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import ExecutionOrder


class DuplicateOrderError(Exception):
    """Raised when an order with the same client_order_id has already been sent."""
    pass


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

    def _reserve_order(self, trade_id: str, tenant: str, client_order_id: str,
                        side: str, quantity: float, price: float, order_type: str):
        """
        Atomically reserve a row for this client_order_id before any network call is made.
        The unique constraint on client_order_id is the source of truth for idempotency,
        not application-level branching, so this is safe under concurrent retries or
        duplicate requests from the caller.
        """
        db = SyncSessionLocal()
        try:
            order = ExecutionOrder(
                trade_id=trade_id,
                tenant=tenant,
                client_order_id=client_order_id,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                status="PENDING",
            )
            db.add(order)
            db.commit()
            return order.id
        except IntegrityError as e:
            db.rollback()
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.info(f"Duplicate client_order_id rejected: {client_order_id}")
                raise DuplicateOrderError(client_order_id) from e
            logger.error(f"Order reservation integrity error: {e}")
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Order reservation failed: {e}")
            raise
        finally:
            db.close()

    def _update_order_status(self, client_order_id: str, status: str, gateway_response=None,
                              external_order_id: str = None):
        db = SyncSessionLocal()
        try:
            order = db.query(ExecutionOrder).filter(
                ExecutionOrder.client_order_id == client_order_id
            ).first()
            if order:
                order.status = status
                if gateway_response is not None:
                    order.gateway_response = gateway_response
                if external_order_id is not None:
                    order.external_order_id = external_order_id
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update order status for {client_order_id}: {e}")
        finally:
            db.close()

    def _send_to_gateway(self, client_order_id: str, side: str, quantity: float,
                          price: float, order_type: str):
        """
        Fires the order at the FIX gateway. client_order_id is sent as ClOrdID so the
        gateway itself can also dedupe on its side (defense in depth) — retries reuse
        the SAME ClOrdID rather than generating a new one per attempt.
        """
        @self.cb
        def _send():
            payload = {
                "ClOrdID": client_order_id,
                "Side": side,
                "OrderQty": quantity,
                "Price": price,
                "OrdType": order_type,
                "SenderCompID": self.sender_comp,
                "TargetCompID": self.target_comp,
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}
            last_exc = None
            for attempt in range(self.max_retries):
                try:
                    resp = requests.post(f"{self.fix_url}/order", json=payload, headers=headers, timeout=10)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_exc = e
                    logger.warning(f"Execution attempt {attempt + 1} failed for {client_order_id}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            raise last_exc
        return _send()

    def send_order(self, trade_id: str, tenant: str, side: str, quantity: float,
                    price: float, order_type: str = "LIMIT", client_order_id: str = None):
        """
        Synchronous entrypoint. Call this from a worker thread, Celery task, or via
        send_order_async from an async route — never call it directly from an async
        def, since it blocks on network I/O and time.sleep.
        """
        if not self.enabled:
            logger.info(f"Execution disabled, would send order {trade_id}")
            return {"status": "SIMULATED"}

        client_order_id = client_order_id or f"{trade_id}:{uuid.uuid4().hex[:12]}"

        try:
            self._reserve_order(trade_id, tenant, client_order_id, side, quantity, price, order_type)
        except DuplicateOrderError:
            db = SyncSessionLocal()
            try:
                existing = db.query(ExecutionOrder).filter(
                    ExecutionOrder.client_order_id == client_order_id
                ).first()
                return {
                    "status": "DUPLICATE",
                    "client_order_id": client_order_id,
                    "existing_status": existing.status if existing else None,
                }
            finally:
                db.close()

        try:
            result = self._send_to_gateway(client_order_id, side, quantity, price, order_type)
            self._update_order_status(
                client_order_id,
                status=result.get("status", "SENT") if isinstance(result, dict) else "SENT",
                gateway_response=result if isinstance(result, dict) else None,
                external_order_id=result.get("order_id") if isinstance(result, dict) else None,
            )
            return result
        except Exception as e:
            self._update_order_status(client_order_id, status="FAILED", gateway_response={"error": str(e)})
            raise

    async def send_order_async(self, trade_id: str, tenant: str, side: str, quantity: float,
                                price: float, order_type: str = "LIMIT", client_order_id: str = None):
        """
        Async-safe wrapper for use inside FastAPI route handlers. Offloads the blocking
        DB + network + retry-sleep work to a thread so the event loop stays free.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.send_order(trade_id, tenant, side, quantity, price, order_type, client_order_id),
        )
