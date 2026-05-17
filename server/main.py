import os
from contextlib import asynccontextmanager
from decimal import Decimal

import pyotp
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine, get_db
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

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/sensor_data", dependencies=[Depends(verify_totp)])
def receive_sensor_data(data: SensorData, db: Session = Depends(get_db)):
    logger.info("sensor_id={id} temperature={temp}", id=data.sensor_id, temp=data.temperature)
    record = Tmprtr(sensor_id=data.sensor_id, tmprtr=Decimal(str(data.temperature)))
    db.add(record)
    db.commit()
    return {"status": "ok"}
