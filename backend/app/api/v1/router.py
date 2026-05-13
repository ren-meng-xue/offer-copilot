from fastapi import APIRouter

from backend.app.modules.auth.router import router as auth_router
from backend.app.modules.debug.router import router as debug_router
from backend.app.modules.events.router import router as events_router
from backend.app.modules.knowledge.router import router as knowledge_router
from backend.app.modules.qa.router import router as qa_router
from backend.app.modules.users.router import router as users_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(knowledge_router)
router.include_router(qa_router)
router.include_router(events_router)
router.include_router(debug_router)
