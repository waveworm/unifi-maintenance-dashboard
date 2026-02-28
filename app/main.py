import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.config import validate_configuration, ensure_directories
from app.logging_config import setup_logging
from app.database import init_db
from app.routers import devices, scheduler, clients, inventory
from app.scheduler_engine import scheduler_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    
    # Startup
    logger.info("🚀 Starting UniFi Maintenance Dashboard")
    
    # Ensure directories exist
    ensure_directories()
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("✅ Database initialized")
    
    # Start scheduler engine
    await scheduler_engine.start()
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down UniFi Maintenance Dashboard")
    await scheduler_engine.stop()


# Setup logging first
setup_logging()

# Validate configuration
settings = validate_configuration()

# Create FastAPI app
app = FastAPI(
    title="UniFi Maintenance Dashboard",
    description="Self-hosted dashboard for managing UniFi network devices",
    version="1.0.0",
    lifespan=lifespan
)


@app.middleware("http")
async def disable_cache_in_dev(request: Request, call_next):
    """Disable browser caching in development for UI and static assets."""
    response = await call_next(request)

    if settings.development_mode and (
        request.url.path.startswith("/static/")
        or request.url.path in {"/", "/schedules", "/clients", "/inventory"}
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


# CORS middleware (for development)
if settings.development_mode:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(devices.router, prefix="/api", tags=["devices"])
app.include_router(scheduler.router, prefix="/api", tags=["scheduler"])
app.include_router(clients.router, prefix="/api", tags=["clients"])
app.include_router(inventory.router, prefix="/api", tags=["inventory"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard UI."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/schedules", response_class=HTMLResponse)
async def schedules_page(request: Request):
    """Render the schedules page."""
    return templates.TemplateResponse(
        "schedules.html",
        {
            "request": request,
            "scheduler_timezone": settings.app_timezone,
        },
    )


@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request):
    """Render the client blocking page."""
    return templates.TemplateResponse("clients.html", {"request": request})


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    """Render the MSP inventory page."""
    return templates.TemplateResponse("inventory.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "phase": "1"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.development_mode
    )
