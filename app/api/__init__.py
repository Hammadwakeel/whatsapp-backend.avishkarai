from app.api.auth import router as auth_router
from app.api.wiki import router as wiki_router

__all__ = ["auth_router", "wiki_router"]