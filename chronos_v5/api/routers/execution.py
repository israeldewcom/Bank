from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from chronos_v5.settlement_execution import SettlementExecution
from chronos_v5.api.dependencies import get_api_key

router = APIRouter()
executor = SettlementExecution()

class OrderRequest(BaseModel):
    trade_id: str
    side: str
    quantity: float
    price: float
    order_type: str = "LIMIT"

@router.post("/order", dependencies=[Depends(get_api_key)])
def place_order(order: OrderRequest):
    result = executor.send_order(order.trade_id, order.side, order.quantity, order.price, order.order_type)
    return result
