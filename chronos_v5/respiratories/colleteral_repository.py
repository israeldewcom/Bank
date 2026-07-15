from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import CollateralHolding

class CollateralRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_by_counterparty(self, counterparty_id):
        return self.db.query(CollateralHolding).filter(CollateralHolding.counterparty_id == counterparty_id).all()

    def update_eligibility(self, collateral_id, eligible):
        holding = self.db.query(CollateralHolding).filter(CollateralHolding.id == collateral_id).first()
        if holding:
            holding.eligible = eligible
            self.db.commit()
        return holding
