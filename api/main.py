"""FastAPI app: routers, CORS, lifespan. PySpark analytics edition."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth_router, frontend_adapter, health, models, predictions, sessions
from routers import analytics_router, alerts, reports
from ws_manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SleepSense AI API starting up (PySpark edition)...")
    init_db()

    # MQTT relay is optional — only active when paho-mqtt is installed
    loop = asyncio.get_event_loop()
    try:
        ws_manager.start_mqtt(loop)
    except Exception as e:
        logger.warning("MQTT relay not started (hardware mode disabled): %s", e)

    yield

    logger.info("SleepSense AI API shutting down...")
    ws_manager.stop_mqtt()


app = FastAPI(
    title="SleepSense AI API",
    version="2.0.0",
    description=(
        "Scalable Sleep Analytics and Risk Screening Using PySpark. "
        "DISCLAIMER: All risk indicators and sleep scores are analytical screening tools "
        "and do NOT constitute a medical diagnosis."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://sleepsense.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy routers (preserved for backward compatibility)
app.include_router(auth_router.router)
app.include_router(sessions.router)
app.include_router(predictions.router)
app.include_router(models.router)
app.include_router(health.router)
app.include_router(frontend_adapter.router)

# New PySpark-era routers
app.include_router(analytics_router.router)
app.include_router(alerts.router)
app.include_router(reports.router)


@app.websocket("/ws/live/{sid}")
async def websocket_live(sid: str, websocket: WebSocket):
    await ws_manager.connect(sid, websocket)
    logger.info("WebSocket connected: session %s", sid)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(sid, websocket)
        logger.info("WebSocket disconnected: session %s", sid)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
