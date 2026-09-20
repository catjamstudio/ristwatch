import platform
import sys

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> dict:
    service = request.app.state.telemetry
    snapshots = service.snapshots()
    statuses = [item.telemetry.status for item in snapshots]
    overall = "healthy"
    if not snapshots or all(status == "offline" for status in statuses):
        overall = "offline"
    elif any(status == "unstable" for status in statuses):
        overall = "unstable"
    elif any(status == "degraded" for status in statuses):
        overall = "degraded"
    return {"status": overall, "streams": len(snapshots)}


@router.get("/api/system")
async def system(request: Request) -> dict:
    config = request.app.state.config
    return {
        "name": "RISTWatch",
        "version": request.app.version,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "mock_telemetry": config.mock_telemetry,
        "rist_enabled": config.rist_enabled,
        "receiver_running": request.app.state.telemetry.process.running,
        "sender_running": request.app.state.telemetry.forwarder.running,
        "image_revision": "unknown",
        "last_config_reload": config.config_dir.joinpath("config.yaml").stat().st_mtime,
        "config_directory": str(config.config_dir),
    }


@router.get("/api/relay")
async def relay(request: Request) -> dict:
    service = request.app.state.telemetry
    return {
        "status": "running" if service.forwarder.running else "stopped",
        "output_url": "rist://@:5556?cname=ristwatch-relay",
        "receiver_running": service.process.running,
        "sender_running": service.forwarder.running,
    }


@router.get("/api/streams")
async def streams(request: Request) -> list[dict]:
    return [snapshot.model_dump(mode="json") for snapshot in request.app.state.telemetry.snapshots()]


@router.get("/api/streams/{stream_id}")
async def stream_detail(stream_id: str, request: Request) -> dict:
    snapshot = request.app.state.telemetry.get(stream_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Stream not found")
    return snapshot.model_dump(mode="json")


@router.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for snapshots in websocket.app.state.telemetry.stream():
            await websocket.send_json(
                {"streams": [snapshot.model_dump(mode="json") for snapshot in snapshots]}
            )
    except WebSocketDisconnect:
        return

