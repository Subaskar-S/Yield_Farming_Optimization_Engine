"""
Main FastAPI application for AI-driven yield farming optimization platform.
Provides REST API endpoints for vault management, strategy optimization, and user interactions.
"""

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import uvicorn
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
from contextlib import asynccontextmanager

# Import our modules
from .routers import vaults, strategies, users, analytics, automation
from .dependencies import get_current_user, get_web3_service, get_ml_service
from ..database.database import engine, Base
from ..services.web3_service import Web3Service
from ..services.ml_service import MLService
from ..services.vault_service import VaultService
from ..services.user_service import UserService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global services
web3_service: Optional[Web3Service] = None
ml_service: Optional[MLService] = None
vault_service: Optional[VaultService] = None
user_service: Optional[UserService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AI Yield Farming API...")
    
    # Initialize database
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")
    
    # Initialize services
    global web3_service, ml_service, vault_service, user_service
    
    try:
        # Web3 service
        web3_service = Web3Service(
            provider_url=os.getenv('INFURA_API_KEY', 'http://localhost:8545'),
            private_key=os.getenv('PRIVATE_KEY')
        )
        await web3_service.initialize()
        logger.info("Web3 service initialized")
        
        # ML service
        ml_service = MLService()
        await ml_service.initialize()
        logger.info("ML service initialized")
        
        # Vault service
        vault_service = VaultService(web3_service, ml_service)
        logger.info("Vault service initialized")
        
        # User service
        user_service = UserService()
        logger.info("User service initialized")
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Yield Farming API...")
    
    # Cleanup services
    if web3_service:
        await web3_service.cleanup()
    if ml_service:
        await ml_service.cleanup()
    
    logger.info("Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="AI-Driven Yield Farming Optimization API",
    description="REST API for automated DeFi yield farming with AI optimization",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Include routers
app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["users"]
)

app.include_router(
    vaults.router,
    prefix="/api/v1/vaults",
    tags=["vaults"]
)

app.include_router(
    strategies.router,
    prefix="/api/v1/strategies",
    tags=["strategies"]
)

app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["analytics"]
)

app.include_router(
    automation.router,
    prefix="/api/v1/automation",
    tags=["automation"]
)

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI-Driven Yield Farming Optimization API",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    # Check Web3 service
    if web3_service:
        try:
            is_connected = await web3_service.is_connected()
            health_status["services"]["web3"] = {
                "status": "healthy" if is_connected else "unhealthy",
                "connected": is_connected
            }
        except Exception as e:
            health_status["services"]["web3"] = {
                "status": "unhealthy",
                "error": str(e)
            }
    else:
        health_status["services"]["web3"] = {"status": "not_initialized"}
    
    # Check ML service
    if ml_service:
        try:
            model_status = await ml_service.get_model_status()
            health_status["services"]["ml"] = {
                "status": "healthy",
                "models": model_status
            }
        except Exception as e:
            health_status["services"]["ml"] = {
                "status": "unhealthy",
                "error": str(e)
            }
    else:
        health_status["services"]["ml"] = {"status": "not_initialized"}
    
    # Determine overall status
    service_statuses = [
        service.get("status", "unknown") 
        for service in health_status["services"].values()
    ]
    
    if any(status == "unhealthy" for status in service_statuses):
        health_status["status"] = "degraded"
    elif any(status == "not_initialized" for status in service_statuses):
        health_status["status"] = "initializing"
    
    return health_status

@app.get("/api/v1/system/info")
async def system_info():
    """Get system information"""
    
    info = {
        "api_version": "1.0.0",
        "environment": os.getenv("NODE_ENV", "development"),
        "blockchain_network": os.getenv("CHAIN_ID", "1"),
        "features": {
            "ai_predictions": True,
            "automated_rebalancing": True,
            "multi_protocol_support": True,
            "risk_management": True,
            "circuit_breakers": True
        },
        "supported_protocols": [
            "Compound",
            "Aave",
            "Yearn Finance",
            "Uniswap V3"
        ],
        "supported_tokens": [
            "USDC",
            "USDT", 
            "DAI",
            "ETH",
            "WBTC"
        ]
    }
    
    return info

@app.get("/api/v1/system/metrics")
async def system_metrics():
    """Get system performance metrics"""
    
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "uptime": "calculated_uptime",  # Would calculate actual uptime
        "requests": {
            "total": 0,  # Would track actual requests
            "success_rate": 0.99
        },
        "blockchain": {},
        "ml_models": {},
        "automation": {}
    }
    
    # Get Web3 metrics
    if web3_service:
        try:
            web3_metrics = await web3_service.get_metrics()
            metrics["blockchain"] = web3_metrics
        except Exception as e:
            logger.error(f"Failed to get Web3 metrics: {str(e)}")
    
    # Get ML metrics
    if ml_service:
        try:
            ml_metrics = await ml_service.get_metrics()
            metrics["ml_models"] = ml_metrics
        except Exception as e:
            logger.error(f"Failed to get ML metrics: {str(e)}")
    
    return metrics

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "timestamp": datetime.now().isoformat()
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "timestamp": datetime.now().isoformat()
            }
        }
    )

# Dependency providers
def get_web3_service_dependency():
    """Get Web3 service dependency"""
    if not web3_service:
        raise HTTPException(
            status_code=503,
            detail="Web3 service not available"
        )
    return web3_service

def get_ml_service_dependency():
    """Get ML service dependency"""
    if not ml_service:
        raise HTTPException(
            status_code=503,
            detail="ML service not available"
        )
    return ml_service

def get_vault_service_dependency():
    """Get vault service dependency"""
    if not vault_service:
        raise HTTPException(
            status_code=503,
            detail="Vault service not available"
        )
    return vault_service

def get_user_service_dependency():
    """Get user service dependency"""
    if not user_service:
        raise HTTPException(
            status_code=503,
            detail="User service not available"
        )
    return user_service

# Background tasks
@app.post("/api/v1/system/tasks/data-collection")
async def trigger_data_collection(background_tasks: BackgroundTasks):
    """Trigger background data collection"""
    
    async def collect_data():
        """Background data collection task"""
        try:
            if ml_service:
                await ml_service.collect_training_data()
                logger.info("Data collection completed")
        except Exception as e:
            logger.error(f"Data collection failed: {str(e)}")
    
    background_tasks.add_task(collect_data)
    
    return {
        "message": "Data collection task started",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/system/tasks/model-training")
async def trigger_model_training(background_tasks: BackgroundTasks):
    """Trigger background model training"""
    
    async def train_models():
        """Background model training task"""
        try:
            if ml_service:
                await ml_service.retrain_models()
                logger.info("Model training completed")
        except Exception as e:
            logger.error(f"Model training failed: {str(e)}")
    
    background_tasks.add_task(train_models)
    
    return {
        "message": "Model training task started",
        "timestamp": datetime.now().isoformat()
    }

# WebSocket endpoints for real-time updates
@app.websocket("/ws/vault/{vault_id}")
async def vault_websocket(websocket, vault_id: str):
    """WebSocket endpoint for real-time vault updates"""
    await websocket.accept()
    
    try:
        while True:
            # Send real-time vault data
            if vault_service:
                vault_data = await vault_service.get_vault_realtime_data(vault_id)
                await websocket.send_json(vault_data)
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("NODE_ENV") == "development",
        log_level="info"
    )
