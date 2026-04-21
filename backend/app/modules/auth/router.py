from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/health")
async def auth_health():
    return {"module": "auth", "status": "ok"}
