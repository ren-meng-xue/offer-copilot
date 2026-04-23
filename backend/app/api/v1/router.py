from fastapi import APIRouter

from backend.app.modules.auth.router import router as auth_router
from backend.app.modules.users.router import router as users_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
