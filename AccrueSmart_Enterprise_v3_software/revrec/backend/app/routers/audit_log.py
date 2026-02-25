from fastapi import APIRouter
from ..auth import require

router = APIRouter(prefix="/audit-log", tags=["audit-log"])

@router.get("/events")
@require(perms=["reports.memo"])
def list_audit_events():
    # Replace with DB query later
    return {
        "rows": [
            {
                "timestamp": "2026-02-21T10:15:00Z",
                "user": "jay@demo.co",
                "module": "contracts",
                "entity_id": "C-1001",
                "action": "UPDATE",
                "field": "transaction_price",
                "old_value": "45000",
                "new_value": "50000",
            },
            {
                "timestamp": "2026-02-21T10:18:00Z",
                "user": "jay@demo.co",
                "module": "contracts",
                "entity_id": "C-1001",
                "action": "UPDATE",
                "field": "start_date",
                "old_value": "2025-01-01",
                "new_value": "2025-02-01",
            },
        ],
        "count": 2,
    }
