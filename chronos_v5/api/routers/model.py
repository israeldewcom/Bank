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
