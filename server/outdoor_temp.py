#!/usr/bin/env python3
"""OpenWeatherMap から推定屋外気温を取得して DB に保存する。cron で 5 分ごとに実行する。"""
import json
import os
import urllib.parse
import urllib.request
from decimal import Decimal

from dotenv import load_dotenv
load_dotenv()

from loguru import logger

from database import SessionLocal
from models import Tmprtr

logger.add("logs/outdoor_temp_{time}.log", rotation="10 MB", compression="zip", retention="30 days")

SENSOR_ID = "EstimatedOutdoor"
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


def fetch_outdoor_temp() -> float:
    api_key = os.environ.get("OWM_API_KEY", "")
    city = os.environ.get("OWM_CITY", "Kasukabe,JP")
    if not api_key:
        raise ValueError("OWM_API_KEY が .env に設定されていません")
    params = urllib.parse.urlencode({"q": city, "appid": api_key, "units": "metric"})
    with urllib.request.urlopen(f"{OWM_URL}?{params}") as resp:
        data = json.load(resp)
    return float(data["main"]["temp"])


def main():
    try:
        temp = fetch_outdoor_temp()
    except Exception as e:
        logger.error("気温取得失敗: {}", e)
        return

    db = SessionLocal()
    try:
        record = Tmprtr(sensor_id=SENSOR_ID, tmprtr=Decimal(str(round(temp, 3))))
        db.add(record)
        db.commit()
        logger.info("sensor_id={} temperature={}", SENSOR_ID, temp)
    except Exception as e:
        logger.error("DB 書き込み失敗: {}", e)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
