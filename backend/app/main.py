from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import load_config
from app.services.telemetry import TelemetryService


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    app.state.config = config
    app.state.telemetry = TelemetryService(
        streams=config.streams,
        policy=config.health_policy,
        interval=config.telemetry_interval,
        rist_enabled=config.rist_enabled,
        srp_file=str(config.rist_srp_file),
    )
    await app.state.telemetry.start()
    yield
    await app.state.telemetry.stop()


app = FastAPI(title="RISTWatch API", version="0.1.0", lifespan=lifespan)
app.include_router(router)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
assets_dir = frontend_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": "RISTWatch", "api_docs": "/docs"}

