from app.api.auth import router as auth_router
from app.api.standards import router as standards_router
from app.api.quiz import router as quiz_router

__all__ = ["auth_router", "standards_router", "quiz_router"]
