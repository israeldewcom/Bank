# chronos_v5/api/routers/advanced.py
# SECURITY FIX: get_admin_user only checks role, not tenant, so previously a
# tenant-A admin could run rehypothecation optimization and shadow VaR
# against tenant-B's collateral/trades. AdvancedProfitOptimizer and
# ShadowVaR now require a tenant argument (see advanced/advanced_optimizer.py
# and advanced/shadow_var.py) and this router passes admin.tenant into both.
#
# Model backfill training, the CBN feed trigger, and dynamic calibration are
# genuinely global/platform-wide operations (they retrain the single shared
# model, or calibrate from Nigeria-wide market data) — these are correctly
# NOT tenant-scoped, but are now restricted to platform admins specifically
# (role == "developer") rather than any tenant's local admin, since they
# affect every tenant on the platform at once.
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


def get_platform_admin(admin: User = Depends(get_admin_user)):
    """
    Stricter than get_admin_user: only role == 'developer' may trigger
    platform-wide operations that affect every tenant at once (shared model
    retraining, CBN feed triggers, global rate calibration). A tenant's
    local 'admin' role is NOT sufficient here.
    """
    if admin.role != "developer":
        raise HTTPException(status_code=403, detail="Platform admin (developer role) required for this operation")
    return admin


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
    optimizer = AdvancedProfitOptimizer(tenant=admin.tenant)
    result = optimizer.run()
    return {"status": "completed", "result": str(result)}

@router.get("/shadow_var")
def get_shadow_var(desk: Optional[str] = None, admin: User = Depends(get_admin_user)):
    var = ShadowVaR(tenant=admin.tenant)
    data = var.get_shadow_var(desk)
    if not data:
        raise HTTPException(status_code=404, detail="No shadow VaR data")
    return data

@router.post("/shadow_var/compute")
def compute_shadow_var(desk: Optional[str] = None, admin: User = Depends(get_admin_user)):
    var = ShadowVaR(tenant=admin.tenant)
    data = var.compute_shadow_var(desk)
    return data

@router.post("/cbn/trigger")
def trigger_cbn_event(admin: User = Depends(get_platform_admin)):
    from chronos_v5.advanced.cbn_event_listener import cbn_listener
    cbn_listener._check_feed()
    return {"status": "triggered"}

@router.post("/calibrate")
def calibrate_parameters(admin: User = Depends(get_platform_admin)):
    calibrator = DynamicCalibrator()
    success = calibrator.force_calibration()
    return {"status": "calibrated" if success else "failed"}

@router.post("/backfill/train")
def train_from_backfill(admin: User = Depends(get_platform_admin)):
    trainer = BackfillTrainer()
    success = trainer.train()
    return {"status": "training completed" if success else "training failed"}

@router.post("/collateral/break_cycles")
async def break_cycles(admin: User = Depends(get_admin_user)):
    # Placeholder – replace with real logic if you have it
    return {"broken": 0, "message": "No cycles to break"}
