#!/usr/bin/env python3
"""日次レポートスクリプト。cron で毎日 8:00 に実行する。"""
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Sensors, Tmprtr
from slack_notify import slack_post

logger.add("logs/daily_report_{time}.log", rotation="10 MB", compression="zip", retention="30 days")


def build_report(db: Session, now: datetime) -> str:
    """レポートメッセージを組み立てて返す。"""
    sensors = db.query(Sensors).order_by(Sensors.print_order).all()

    latest = {}
    for s in sensors:
        row = (db.query(Tmprtr)
               .filter(Tmprtr.sensor_id == s.sensor_id)
               .order_by(Tmprtr.event_datetime.desc())
               .first())
        if row:
            latest[s.sensor_id] = row

    summary = {}
    for row in db.execute(text("""
        SELECT sensor_id, MAX(tmprtr) AS max_t, MIN(tmprtr) AS min_t, AVG(tmprtr) AS avg_t
        FROM tmprtr
        WHERE event_datetime >= NOW() - INTERVAL 24 HOUR
        GROUP BY sensor_id
    """)):
        summary[row.sensor_id] = row

    anomalies = [row[0] for row in db.execute(text("""
        SELECT text FROM notifications
        WHERE last_ng_event >= NOW() - INTERVAL 24 HOUR
    """))]

    lines = [f"[日次レポート] {now.strftime('%Y-%m-%d %H:%M')}", ""]

    lines.append("■ 最新値")
    latest_parts = []
    for s in sensors:
        name = s.print_name or s.sensor_id
        if s.sensor_id in latest:
            t = f"{float(latest[s.sensor_id].tmprtr):.1f}"
            latest_parts.append(f"{name}: {t}°C")
        else:
            latest_parts.append(f"{name}: N/A")
    lines.append(" / ".join(latest_parts))
    lines.append("")

    lines.append("■ 24時間サマリー")
    for s in sensors:
        name = s.print_name or s.sensor_id
        if s.sensor_id in summary:
            row = summary[s.sensor_id]
            lines.append(
                f"{name}: {float(row.min_t):.1f}〜{float(row.max_t):.1f}°C"
                f" (平均 {float(row.avg_t):.1f}°C)"
            )
        else:
            lines.append(f"{name}: データなし")
    lines.append("")

    lines.append("■ 異常: " + (", ".join(anomalies) if anomalies else "なし"))

    return "\n".join(lines)


def run() -> None:
    now = datetime.now()
    logger.info("Start")
    db = SessionLocal()
    try:
        message = build_report(db, now)
        logger.info(f"Message:\n{message}")
        slack_post(message)
    finally:
        db.close()
    logger.info("End")


if __name__ == "__main__":
    run()
