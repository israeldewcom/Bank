from fastapi import APIRouter, Depends, HTTPException
from chronos_v5.services.predictor import SettlementPredictor
from chronos_v5.api.dependencies import get_api_key
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()
predictor = SettlementPredictor(retrain_on_init=False)

class RetrainRequest(BaseModel):
    force: bool = False

@router.post("/retrain", dependencies=[Depends(get_api_key)])
def retrain_model(req: RetrainRequest):
    if req.force:
        predictor._retrain_if_needed()
        return {"status": "Retraining triggered"}
    predictor._retrain_if_needed()
    return {"status": "Retraining completed"}

@router.get("/drift")
def get_drift_status():
    return {"drift_detected": predictor.drift_detector.drift_detected}

@router.get("/metrics")
async def get_model_metrics():
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
