# chronos_v5/api/routers/advanced_extras.py
from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.advanced.cbn_event_listener import cbn_listener
from chronos_v5.advanced.backfill_trainer import BackfillTrainer
from chronos_v5.advanced.advanced_optimizer import AdvancedProfitOptimizer
from chronos_v5.advanced.dynamic_pricing import DynamicPricingEngine
from chronos_v5.logger_setup import logger

router = APIRouter(prefix="/advanced", tags=["Advanced Extras"])

@router.post("/calibrate")
def force_calibration(admin: User = Depends(get_admin_user)):
    calibrator = DynamicCalibrator()
    success = calibrator.force_calibration()
    if success:
        return {"status": "calibrated"}
    else:
        raise HTTPException(500, "Calibration failed")

@router.post("/cbn/trigger")
def trigger_cbn_event(admin: User = Depends(get_admin_user)):
    try:
        cbn_listener._check_feed()
        return {"status": "triggered"}
    except Exception as e:
        logger.error(f"CBN trigger failed: {e}")
        raise HTTPException(500, f"CBN trigger failed: {str(e)}")

@router.post("/backfill/train")
def train_from_backfill(admin: User = Depends(get_admin_user)):
    trainer = BackfillTrainer()
    success = trainer.train()
    if success:
        return {"status": "training started"}
    else:
        raise HTTPException(500, "Backfill training failed")

@router.post("/collateral/break_cycles")
def break_collateral_cycles(admin: User = Depends(get_admin_user)):
    # Placeholder – implement actual cycle breaking logic
    return {"broken": 0, "message": "Cycle breaking not implemented yet"}

@router.post("/pricing/dynamic")
def dynamic_pricing(
    counterparty_id: str,
    instrument_type: str,
    notional: float,
    admin: User = Depends(get_admin_user)
):
    engine = DynamicPricingEngine()
    price = engine.get_client_price(counterparty_id, instrument_type, notional)
    return price
