from chronos_v5.config import Config
from chronos_v5.nigeria_adapter import nigeria
from chronos_v5.haircut_engine import HaircutEngine
from chronos_v5.logger_setup import logger
import asyncio

class PricingEngine:
    def __init__(self):
        self.spread_base = Config.PRICING_SPREAD_BASELINE
        self.min_fee = Config.MIN_FEE_PER_TRADE
        self.haircut_engine = HaircutEngine()

    def get_client_price(self, counterparty_id: str, instrument_type: str, notional: float) -> dict:
        spread = self.spread_base
        risk_factor = 1.0
        mpr = nigeria.cbn_mpr
        haircut = self.haircut_engine.compute_haircut(instrument_type)
        fee = max(notional * (spread + haircut/2), self.min_fee)
        price = {
            "gross_price": notional,
            "spread": spread,
            "haircut_applied": haircut,
            "fee": fee,
            "net_price": notional - fee,
            "currency": "NGN"
        }
        return price

    async def get_client_price_async(self, counterparty_id: str, instrument_type: str, notional: float) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_client_price, counterparty_id, instrument_type, notional)
