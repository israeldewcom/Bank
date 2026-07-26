from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.advanced.advanced_optimizer import AdvancedProfitOptimizer
from chronos_v5.advanced.shadow_var import ShadowVaR
from chronos_v5.advanced.dynamic_pricing import DynamicPricingEngine
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.advanced.backfill_trainer import BackfillTrainer
from chronos_v5.models import User
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/advanced", tags=["Advanced"])

class PricingQuoteRequest(BaseModel):
    counterparty_id: str
    instrument_type: str
    notional: float

@router.post("/pricing/dynamic")
def dynamic_quote(req: PricingQuoteRequest, admin: User = Depends(get_admin_user)):
    engine = DynamicPricingEngine()
    price = engine.get_client_price(req.counterparty_id, req.instrument_type, req.notional)
    return price

@router.post("/optimize/rehypothecation")
def run_lp_optimizer(admin: User = Depends(get_admin_user)):
    optimizer = AdvancedProfitOptimizer()
    result = optimizer.run()
    return {"status": "completed", "result": str(result)}

@router.get("/shadow_var")
def get_shadow_var(desk: Optional[str] = None, admin: User = Depends(get_admin_user)):
    var = ShadowVaR()
    data = var.get_shadow_var(desk)
    if not data:
        raise HTTPException(status_code=404, detail="No shadow VaR data")
    return data

@router.post("/shadow_var/compute")
def compute_shadow_var(desk: Optional[str] = None, admin: User = Depends(get_admin_user)):
    var = ShadowVaR()
    data = var.compute_shadow_var(desk)
    return data

@router.post("/cbn/trigger")
def trigger_cbn_event(admin: User = Depends(get_admin_user)):
    from chronos_v5.advanced.cbn_event_listener import cbn_listener
    cbn_listener._check_feed()
    return {"status": "triggered"}

@router.post("/calibrate")
def calibrate_parameters(admin: User = Depends(get_admin_user)):
    calibrator = DynamicCalibrator()
    success = calibrator.force_calibration()
    return {"status": "calibrated" if success else "failed"}

@router.post("/backfill/train")
def train_from_backfill(admin: User = Depends(get_admin_user)):
    trainer = BackfillTrainer()
    success = trainer.train()
    return {"status": "training completed" if success else "training failed"}

@router.post("/collateral/break_cycles")
async def break_cycles(admin: User = Depends(get_admin_user)):
    # Placeholder – replace with real logic if you have it
    return {"broken": 0, "message": "No cycles to break"}
