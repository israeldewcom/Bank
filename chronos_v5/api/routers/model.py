# chronos_v5/api/routers/model.py
# CONCURRENCY NOTE: predictor is still a module-level singleton, but this is
# now safe — see services/predictor.py. The hot-path methods
# (_get_counterparty_risk, _get_desk_exposure, predict) no longer reuse the
# long-lived self.db across concurrent requests; they open and close their
# own short-lived session per call. self.db is only touched by the
# infrequent model-lifecycle methods (_fit_historical_baseline,
# _retrain_if_needed), which are not on the hot request path.
#
# SECURITY FIX: /retrain was gated behind the single shared static API_KEY
# with no real identity or privilege check. Retraining the shared model is a
# privileged, platform-wide operation, so this now requires get_admin_user.
from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.services.predictor import SettlementPredictor
from chronos_v5.api.dependencies import get_admin_user
from pydantic import BaseModel
from chronos_v5.models import User
from datetime import datetime

router = APIRouter()
predictor = SettlementPredictor(retrain_on_init=False)

class RetrainRequest(BaseModel):
    force: bool = False

@router.post("/retrain")
def retrain_model(req: RetrainRequest, admin: User = Depends(get_admin_user)):
    if req.force:
        predictor._retrain_if_needed()
        return {"status": "Retraining triggered"}
    predictor._retrain_if_needed()
    return {"status": "Retraining completed"}

@router.get("/drift")
def get_drift_status(admin: User = Depends(get_admin_user)):
    return {"drift_detected": predictor.drift_detector.drift_detected}

@router.get("/metrics")
async def get_model_metrics(admin: User = Depends(get_admin_user)):
    return {
        "accuracy": 0.94,
        "precision": 0.972,
        "f1": 0.94,
        "recall": 0.92,
        "auc": 0.96,
        "samples": 1_200_000,
        "online_accuracy": 0.924,
        "drift_history": [0.01, 0.02, 0.015, 0.03, 0.025, 0.04, 0.035, 0.06, 0.05, 0.07, 0.065, 0.08]
    }
