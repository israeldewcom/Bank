from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import CollateralHolding


class CollateralRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_counterparty(self, counterparty_id, tenant: str):
        q = self.db.query(CollateralHolding).filter(
            CollateralHolding.counterparty_id == counterparty_id,
            CollateralHolding.tenant == tenant,
        )
        return q.all()

    def update_eligibility(self, collateral_id, eligible, tenant: str):
        q = self.db.query(CollateralHolding).filter(
            CollateralHolding.id == collateral_id,
            CollateralHolding.tenant == tenant,
        )
        holding = q.first()
        if holding:
            holding.eligible = eligible
            self.db.commit()
        return holding
