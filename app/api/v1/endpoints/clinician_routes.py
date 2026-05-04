from fastapi import APIRouter

router = APIRouter(prefix="/clinicians", tags=["Clinicians"])

@router.get(
    "/",
    summary="List clinicians (Stub)",
)
def list_clinicians():
    """
    Stub for listing active clinicians.
    """
    return {"success": True, "items": []}
