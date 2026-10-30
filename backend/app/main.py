from fastapi import FastAPI
from backend.app.routers.movement import router as movement_router
from backend.app.schemas.movement import AutonomyCapabilities

app = FastAPI(
    title="DORURU Robot Backend API",
    description="Backend AI Orchestrator and Device Communication Service for DORURU",
    version="1.0.0",
)

# Register Routers
app.include_router(movement_router)


@app.get("/")
async def root():
    return {
        "robot": "DORURU",
        "description": "Educational & Lab Assistant Robot",
        "status": "online",
        "autonomy_level": 1,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "autonomy": AutonomyCapabilities().model_dump(),
    }

