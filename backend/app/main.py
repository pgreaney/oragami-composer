"""
FastAPI application entry point for Origami Composer
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.connection import engine, Base
from app.api.routes import auth, oauth
from app.graphql.schema import create_graphql_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Manage application lifecycle events
    """
    # Startup
    print("Starting Origami Composer API...")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug mode: {settings.DEBUG}")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified")
    
    # Add Redis connection initialization here in Step 9
    yield
    
    # Shutdown
    print("Shutting down Origami Composer API...")
    # Add cleanup code here


# Create FastAPI application
app = FastAPI(
    title="Origami Composer API",
    description="Algorithmic Trading Platform - Paper Trading Only",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "Origami Composer API",
        "version": "0.1.0",
        "status": "healthy",
        "paper_trading_only": True,
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "api": "operational",
        "database": "operational",
        "redis": "pending",  # Will be updated in Step 9
        "market_data": "pending",  # Will be updated in Step 7
    }


# GraphQL endpoint
graphql_router = create_graphql_router()
app.include_router(graphql_router, prefix="/graphql")

# Authentication routes
app.include_router(auth.router, prefix="/api")

# OAuth routes
app.include_router(oauth.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Additional startup logging"""
    print("GraphQL endpoint available at: /graphql")
    print("GraphiQL interface available at: /graphql")
    print("REST API docs available at: /api/docs")
    print("Authentication endpoints available at: /api/auth/*")
    print("OAuth endpoints available at: /api/oauth/*")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
