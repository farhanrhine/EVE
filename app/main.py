from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, centres, bookings, payments
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist in case migrations haven't run yet
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created on startup.")
    except Exception as e:
        logger.warning(f"Could not connect to database on startup: {e}")
    yield
    # Shutdown logic if any
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend service for diagnostic test bookings and simulated payments with idempotent webhooks.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for frontend or API consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from pathlib import Path

STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/", tags=["Root"], response_class=HTMLResponse)
def root():
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return HTMLResponse("<h3>EVE Healthcare Service Online</h3><p><a href='/docs'>Swagger API Docs</a></p>")


# Include all routers
app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)
