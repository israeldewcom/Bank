# chronos_v5/api/routers/risk.py — full corrected file
from fastapi import APIRouter, Depends, Query
from chronos_v5.risk_engine import RiskEngine
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import RiskMetrics, User
from chronos_v5.database import SyncSessionLocal

router = APIRouter()
engine = RiskEngine()

@router.get("/metrics")
def get_risk_metrics(desk: str = Query(None), current_user: User = Depends(get_current_user)):
    db = SyncSessionLocal()
    query = db.query(RiskMetrics).filter(RiskMetrics.tenant == current_user.tenant).order_by(RiskMetrics.timestamp.desc())
    if desk:
        query = query.filter(RiskMetrics.desk == desk)
    metrics = query.first()
    db.close()
    if not metrics:
        metric = engine.compute_all(tenant=current_user.tenant, desk=desk)
        return metric
    return metrics

@router.post("/compute")
def compute_risk(desk: str = Query(None), current_user: User = Depends(get_current_user)):
    result = engine.compute_all(tenant=current_user.tenant, desk=desk)
    return result
