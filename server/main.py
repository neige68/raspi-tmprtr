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
        ("6時間 / DS18B20", f"{root}/graph/view?hours=6&sensor=indoor"),
        ("24時間 / DS18B20+外気温", f"{root}/graph/view?hours=24&sensor=other"),
        ("2日間 / DS18B20+外気温", f"{root}/graph/view?hours=48&sensor=other"),
        ("1週間 / DS18B20+外気温", f"{root}/graph/view?hours=168&sensor=other"),
        ("30日間 / DS18B20+外気温", f"{root}/graph/view?hours=720&sensor=other"),
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
    sensor: Literal["all", "cpu", "other", "indoor"] = "all",
    tz: Optional[int] = Query(default=None, ge=-12, le=14),
    start: Optional[datetime] = Query(default=None),
):
    root = request.scope.get("root_path", "")
    start_param = start.isoformat() if start is not None else ""
    # tz 未指定時はブラウザの UTC オフセットを JS で取得、指定時はその値を定数として埋め込む
    tz_expr = str(tz) if tz is not None else "Math.round(-new Date().getTimezoneOffset()/60)"
    html = (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        f"<title>温度グラフ ({hours}h / {sensor})</title>"
        "<script>\n"
        f"var _root='{root}',_hours={hours},_sensor='{sensor}',_start='{start_param}';\n"
        f"function _tz(){{return {tz_expr};}}\n"
        "function buildUrl(){\n"
        "  var u=_root+'/graph?hours='+_hours+'&sensor='+_sensor+'&tz='+_tz();\n"
        "  if(_start)u+='&start='+_start;\n"
        "  return u+'&_='+Date.now();\n"
        "}\n"
        "window.onload=function(){\n"
        "  var g=document.getElementById('g');\n"
        "  function load(){g.src=buildUrl();}\n"
        "  load();\n"
        "  setInterval(load,60000);\n"
        "};\n"
        "</script>"
        "</head><body style='margin:0;background:#000'>"
        "<img id='g' src='' style='width:100%;max-height:100vh;object-fit:contain'>"
        "</body></html>"
    )
    return HTMLResponse(content=html)


@app.get("/graph")
def get_graph(
    hours: int = Query(default=24, ge=1),
    sensor: Literal["all", "cpu", "other", "indoor"] = "all",
    tz: Optional[int] = Query(default=None, ge=-12, le=14),
    start: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        png = generate_graph(db, hours, sensor, tz if tz is not None else 0, start)
        return Response(content=png, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="グラフ生成がタイムアウトしました")
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="グラフ生成に失敗しました")


@app.post("/sensor_data", dependencies=[Depends(verify_totp)])
def receive_sensor_data(data: SensorData, db: Session = Depends(get_db)):
    logger.info("sensor_id={id} temperature={temp}", id=data.sensor_id, temp=data.temperature)
    record = Tmprtr(sensor_id=data.sensor_id, tmprtr=Decimal(str(data.temperature)))
    db.add(record)
    db.commit()
    return {"status": "ok"}
