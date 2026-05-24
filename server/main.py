import os
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

import pyotp
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.responses import HTMLResponse, Response
from fastapi.security import APIKeyHeader
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine, get_db
from graph import generate_graph
from models import Tmprtr

_totp_secret = os.getenv("TOTP_SECRET")
if _totp_secret is None:
    raise ValueError("TOTP_SECRET が .env に設定されていません")
_totp = pyotp.TOTP(_totp_secret)

_totp_header = APIKeyHeader(name="X-TOTP-Code")


def verify_totp(code: str = Security(_totp_header)):
    if not _totp.verify(code, valid_window=1):
        raise HTTPException(status_code=403, detail="Invalid TOTP code")

logger.add(
    "logs/sensor_{time}.log",
    rotation="10 MB",
    compression="zip",
    retention="30 days",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("DB 接続確認 OK")
    yield


app = FastAPI(lifespan=lifespan)

class SensorData(BaseModel):
    sensor_id: str = Field(max_length=30)
    temperature: float = Field(ge=-999.999, le=999.999)

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    root = request.scope.get("root_path", "")
    links = [
        ("6時間 / 全センサー", f"{root}/graph/view?hours=6&sensor=all"),
        ("24時間 / DS18B20", f"{root}/graph/view?hours=24&sensor=other"),
        ("1週間 / DS18B20", f"{root}/graph/view?hours=168&sensor=other"),
    ]
    items = "".join(f"<li><a href='{url}'>{label}</a></li>" for label, url in links)
    html = (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        "<title>温度グラフ</title>"
        "</head><body>"
        "<h1>温度グラフ</h1>"
        f"<ul>{items}</ul>"
        "</body></html>"
    )
    return HTMLResponse(content=html)

@app.get("/graph/view", response_class=HTMLResponse)
def get_graph_view(
    request: Request,
    hours: int = Query(default=24, ge=1),
    sensor: Literal["all", "cpu", "other"] = "all",
    tz: int = Query(default=9, ge=-12, le=14),
    start: Optional[datetime] = Query(default=None),
):
    root = request.scope.get("root_path", "")
    img_url = f"{root}/graph?hours={hours}&sensor={sensor}&tz={tz}"
    if start is not None:
        img_url += f"&start={start.isoformat()}"
    html = (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        "<meta http-equiv='refresh' content='60'>"
        f"<title>温度グラフ ({hours}h / {sensor})</title>"
        "</head><body style='margin:0;background:#000'>"
        f"<img src='{img_url}' style='width:100%'>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


@app.get("/graph")
def get_graph(
    hours: int = Query(default=24, ge=1),
    sensor: Literal["all", "cpu", "other"] = "all",
    tz: int = Query(default=9, ge=-12, le=14),
    start: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        png = generate_graph(db, hours, sensor, tz, start)
        return Response(content=png, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="グラフ生成に失敗しました")


@app.post("/sensor_data", dependencies=[Depends(verify_totp)])
def receive_sensor_data(data: SensorData, db: Session = Depends(get_db)):
    logger.info("sensor_id={id} temperature={temp}", id=data.sensor_id, temp=data.temperature)
    record = Tmprtr(sensor_id=data.sensor_id, tmprtr=Decimal(str(data.temperature)))
    db.add(record)
    db.commit()
    return {"status": "ok"}
