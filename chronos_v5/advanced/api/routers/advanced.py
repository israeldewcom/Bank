from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.api.dependencies import get_api_key
from chronos_v5.advanced.advanced_optimizer import AdvancedProfitOptimizer
from chronos_v5.advanced.shadow_var import ShadowVaR
from chronos_v5.advanced.dynamic_pricing import DynamicPricingEngine
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.advanced.backfill_trainer import BackfillTrainer
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/advanced", tags=["Advanced"])

class PricingQuoteRequest(BaseModel):
    counterparty_id: str
    instrument_type: str
    notional: float

@router.post("/pricing/dynamic", dependencies=[Depends(get_api_key)])
def dynamic_quote(req: PricingQuoteRequest):
    engine = DynamicPricingEngine()
    price = engine.get_client_price(req.counterparty_id, req.instrument_type, req.notional)
    return price

@router.post("/optimize/rehypothecation", dependencies=[Depends(get_api_key)])
def run_lp_optimizer():
    optimizer = AdvancedProfitOptimizer()
    result = optimizer.run()
    return {"status": "completed", "result": str(result)}

@router.get("/shadow_var", dependencies=[Depends(get_api_key)])
def get_shadow_var(desk: Optional[str] = None):
    var = ShadowVaR()
    data = var.get_shadow_var(desk)
    if not data:
        raise HTTPException(status_code=404, detail="No shadow VaR data")
    return data

@router.post("/shadow_var/compute", dependencies=[Depends(get_api_key)])
def compute_shadow_var(desk: Optional[str] = None):
    var = ShadowVaR()
    data = var.compute_shadow_var(desk)
    return data

@router.post("/cbn/trigger", dependencies=[Depends(get_api_key)])
def trigger_cbn_event():
    from chronos_v5.advanced.cbn_event_listener import cbn_listener
    cbn_listener._check_feed()
    return {"status": "triggered"}

@router.post("/calibrate", dependencies=[Depends(get_api_key)])
def calibrate_parameters():
    calibrator = DynamicCalibrator()
    success = calibrator.force_calibration()
    return {"status": "calibrated" if success else "failed"}

@router.post("/backfill/train", dependencies=[Depends(get_api_key)])
def train_from_backfill():
    trainer = BackfillTrainer()
    success = trainer.train()
    return {"status": "training completed" if success else "training failed"}

# ===== ADD THESE TWO ENDPOINTS =====
@router.post("/collateral/break_cycles", dependencies=[Depends(get_api_key)])
async def break_cycles():
    # Placeholder – replace with real logic if you have it
    return {"broken": 0, "message": "No cycles to break"}

# If you also need a separate endpoint for rebalance, it's already covered by /optimize/rehypothecation
