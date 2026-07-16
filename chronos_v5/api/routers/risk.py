from fastapi import APIRouter, Depends, Query
from chronos_v5.risk_engine import RiskEngine
from chronos_v5.api.dependencies import get_api_key
from chronos_v5.models import RiskMetrics
from chronos_v5.database import SyncSessionLocal

router = APIRouter()
engine = RiskEngine()

@router.get("/metrics", dependencies=[Depends(get_api_key)])
def get_risk_metrics(desk: str = Query(None)):
    db = SyncSessionLocal()
    query = db.query(RiskMetrics).order_by(RiskMetrics.timestamp.desc())
    if desk:
        query = query.filter(RiskMetrics.desk == desk)
    metrics = query.first()
    db.close()
    if not metrics:
        metric = engine.compute_all(desk)
        return metric
    return metrics

@router.post("/compute", dependencies=[Depends(get_api_key)])
def compute_risk(desk: str = Query(None)):
    result = engine.compute_all(desk)
    return result
