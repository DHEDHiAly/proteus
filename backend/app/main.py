from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db, close_db
from app.api.auth import router as auth_router
from app.api.runs import router as runs_router
from app.api.targets import router as targets_router
from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.benchmarks import router as benchmarks_router
from app.services.compliance import ComplianceChecker
from app.services.benchmark import load_sota_binders


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await load_sota_binders()
    yield
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-Grade MCMC Protein Design Platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth_router, prefix="/api/v1")
app.include_router(runs_router, prefix="/api/v1")
app.include_router(targets_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(benchmarks_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "service": settings.APP_NAME,
    }


@app.get("/api/v1/disclaimer")
async def get_disclaimer():
    checker = ComplianceChecker()
    return {"disclaimer": checker.get_disclaimer()}


@app.get("/api/v1/check-dual-use")
async def check_dual_use(sequence: str):
    checker = ComplianceChecker()
    return checker.check_dual_use(sequence)
