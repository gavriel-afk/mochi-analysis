"""
FastAPI application for Mochi Analytics.

Version: 2.0.0
"""

import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mochi_analytics.api.models import HealthResponse

# Create FastAPI app
app = FastAPI(
    title="Mochi Analytics API",
    description="Analytics platform for Mochi conversation data",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="2.0.0"
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Mochi Analytics API",
        "version": "2.0.0",
        "docs": "/docs"
    }


# Import and include routers after app is created to avoid circular imports
def setup_routes():
    """Setup API routes."""
    from mochi_analytics.api.routes import (
        analysis,
        exports,
        jobs,
        organizations,
        reports,
        tasks,
    )

    app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
    app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
    app.include_router(exports.router, prefix="/api/v1", tags=["Exports"])
    app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
    app.include_router(organizations.router, prefix="/api/v1", tags=["Organizations"])
    app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])


# Setup routes on startup
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    setup_routes()

    # Initialize database
    from mochi_analytics.storage.database import create_tables
    create_tables()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    pass
