from fastapi import APIRouter
from datetime import datetime, timezone
import time
import tzlocal

router = APIRouter(
    prefix="/time",
    tags=["Time"]
)

@router.get("/server")
async def get_server_time():
    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)

    return {
        "server_time_local": now_local.isoformat(),
        "server_time_utc": now_utc.isoformat(),
        "timezone": str(tzlocal.get_localzone()),
        "unix_timestamp": int(time.time())
    }
