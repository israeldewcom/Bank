from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import CollateralHolding

class CollateralRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_counterparty(self, counterparty_id, tenant: str = None):
        q = self.db.query(CollateralHolding).filter(CollateralHolding.counterparty_id == counterparty_id)
        if tenant is not None:
            q = q.filter(CollateralHolding.tenant == tenant)
        return q.all()

    def update_eligibility(self, collateral_id, eligible, tenant: str = None):
        q = self.db.query(CollateralHolding).filter(CollateralHolding.id == collateral_id)
        if tenant is not None:
            q = q.filter(CollateralHolding.tenant == tenant)
        holding = q.first()
        if holding:
            holding.eligible = eligible
            self.db.commit()
        return holding
