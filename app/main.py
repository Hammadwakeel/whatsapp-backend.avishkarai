from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.api.auth import router as auth_router
from app.api import wiki_router
from app.api.agent import router as agent_router
from app.api.whatsapp import router as whatsapp_router
from app.api.webhook import router as webhook_router
from app.api.booking import router as booking_router
from app.api.journey import router as journey_router
from app.services.journey.auto_scheduler import init_auto_scheduler, get_auto_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - create all tables including new tenant table
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize Journey Auto Scheduler
    async with AsyncSessionLocal() as db:
        await init_auto_scheduler(db)

    yield

    # Shutdown - stop the scheduler
    scheduler = get_auto_scheduler()
    scheduler.shutdown()

    await engine.dispose()


app = FastAPI(
    title="Inika Backend - Multi-Tenant Hotel Platform",
    description="Multi-tenant SaaS platform for hotels with WhatsApp AI agent integration",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(wiki_router)
app.include_router(agent_router)
app.include_router(whatsapp_router)
app.include_router(webhook_router)
app.include_router(booking_router)
app.include_router(journey_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": "inika-backend", "version": "2.0.0"}


@app.get("/")
async def root():
    return {
        "message": "Inika Backend - Multi-Tenant Hotel Platform",
        "version": "2.0.0",
        "docs": "/docs",
        "multi_tenant": True,
    }