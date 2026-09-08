"""PicketIQ Application Entry Point.

Autonomous Business Signal Investigation Platform.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.anomalies import router as anomalies_router

app = FastAPI(
    title="PicketIQ",
    description="Autonomous Business Signal Investigation Platform",
    version="0.1.0",
)

# Configure CORS for Next.js frontend and local environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount health check and API routers
app.include_router(health_router)
app.include_router(anomalies_router, prefix="/api")
