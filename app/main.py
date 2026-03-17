"""FastAPI application entry point for Agent Orchestra."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Agent Orchestra",
    description="Multi-agent orchestration system for building, validating, and marketing SaaS products.",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "Agent Orchestra",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


# Import and include API routes
from app.api.routes import router  # noqa: E402

app.include_router(router, prefix="/api")
