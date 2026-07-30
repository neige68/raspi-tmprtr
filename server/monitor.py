#!/usr/bin/env python3
"""モニタースクリプト。cron で毎分実行する。

notifications テーブル:
  id=1: No Data        — 全センサーの最終受信時刻を監視
  id=2: High Temp      — upper_limit 超えを監視
  id=3: Low Temp       — lower_limit 未満を監視
"""
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Notifications, NotificationIntervals
from slack_notify import slack_post

logger.add("logs/monitor_{time}.log", rotation="10 MB", compression="zip", retention="30 days")


def get_last_event_datetime(db: Session) -> tuple[datetime | None, str | None]:
    """No Data チェック対象センサー（data_check_enabled=True）の最終イベント時刻の
    最小値（最も古いセンサーの最終受信時刻）と、そのセンサーの print_name を返す。"""
    result = db.execute(text("""
        SELECT MAX(t.event_datetime) AS last_event, s.print_name
        FROM tmprtr t JOIN sensors s ON t.sensor_id = s.sensor_id
        WHERE s.data_check_enabled
        GROUP BY t.sensor_id, s.print_name
        ORDER BY last_event ASC
        LIMIT 1
    """)).first()
    if result is None:
        return None, None
    return result[0], result[1]


def update_no_data(db: Session, last_event_datetime: datetime | None, sensor_name: str | None) -> None:
    """id=1: 全センサーの最終受信時刻と、最も古いセンサーの print_name を書き込む。"""
    if last_event_datetime is None:
        return
    db.execute(
        text("UPDATE notifications SET last_ok_event = :dt, sensor_name = :name WHERE id = 1"),
        {"dt": last_event_datetime, "name": sensor_name},
    )
    db.commit()


def _update_limit_check(db: Session, notifications_id: int, where_clause: str,
                        last_event_datetime: datetime | None) -> None:
    """upper/lower limit 違反の最終時刻を last_ng_event に書き込み、2分以上前なら last_ok_event も更新する。"""
    result = db.execute(text(f"""
        SELECT t.event_datetime, t.tmprtr FROM tmprtr t
        JOIN sensors s ON t.sensor_id = s.sensor_id
        WHERE {where_clause}
        ORDER BY t.event_datetime DESC LIMIT 1
    """)).first()

    last_ng_event = result[0] if result else None
    last_ng_tmprtr = result[1] if result else None
    delta_seconds = 120

    if last_ng_event:
        db.execute(
            text("UPDATE notifications SET last_ng_event = :dt, value = :val WHERE id = :id"),
            {"dt": last_ng_event, "val": last_ng_tmprtr, "id": notifications_id},
        )
        if last_event_datetime:
            delta_seconds = (last_event_datetime - last_ng_event).total_seconds()

    if delta_seconds >= 120 and last_event_datetime:
        db.execute(
            text("UPDATE notifications SET last_ok_event = :dt WHERE id = :id"),
            {"dt": last_event_datetime, "id": notifications_id},
        )
    db.commit()


def update_high_temp(db: Session, last_event_datetime: datetime | None) -> None:
    """id=2: upper_limit 超えチェック。"""
    _update_limit_check(
        db, 2,
        "s.upper_limit IS NOT NULL AND t.tmprtr > s.upper_limit",
        last_event_datetime,
    )


def update_low_temp(db: Session, last_event_datetime: datetime | None) -> None:
    """id=3: lower_limit 未満チェック。"""
    _update_limit_check(
        db, 3,
        "s.lower_limit IS NOT NULL AND t.tmprtr < s.lower_limit",
        last_event_datetime,
    )


def _should_notify(now: datetime, delta_seconds: float, last_notification: datetime | None,
                   intervals: list, notifications_id: int) -> bool:
    """通知すべきかを判定する（エスカレーション付き）。"""
    last_interval_seconds = 0
    to_notify = False

    # id > 1 は異常発生直後に即時通知（直近5分以内に通知していなければ）
    if notifications_id > 1:
        if not last_notification or last_notification <= now - timedelta(seconds=300):
            to_notify = True

    for interval in intervals:
        interval_seconds = interval.interval_minutes * 60
        window = interval_seconds - last_interval_seconds
        if delta_seconds >= interval_seconds and (
            not last_notification or last_notification <= now - timedelta(seconds=window)
        ):
            to_notify = True
        last_interval_seconds = interval_seconds

    return to_notify


def check_and_notify(db: Session, now: datetime) -> None:
    """各 notifications を確認し、必要なら Slack 通知を送る。"""
    intervals = db.query(NotificationIntervals).order_by(NotificationIntervals.interval_minutes).all()

    for notifications_id in [1, 2, 3]:
        row = db.query(Notifications).filter(Notifications.id == notifications_id).first()
        if not row or not row.last_ok_event:
            continue
        if row.last_ok_event and row.last_ng_event and row.last_ok_event > row.last_ng_event:
            continue

        delta_seconds = (now - row.last_ok_event).total_seconds()
        logger.info(f"Check id={notifications_id} delta={delta_seconds:.0f}s")

        if _should_notify(now, delta_seconds, row.last_notification, intervals, notifications_id):
            minutes = int(delta_seconds / 60)
            if notifications_id == 1 and row.sensor_name:
                detail_str = f" ({row.sensor_name})"
            elif notifications_id > 1 and row.value is not None:
                detail_str = f" ({row.value:.1f}°C)"
            else:
                detail_str = ""
            message = f"{row.text_}{detail_str}: {minutes} minutes"
            logger.info(f"通知送信: {message}")
            slack_post(message)
            db.execute(
                text("UPDATE notifications SET last_notification = :dt WHERE id = :id"),
                {"dt": now, "id": notifications_id},
            )
            db.commit()


def run() -> None:
    now = datetime.now()
    logger.info("Start")
    db = SessionLocal()
    try:
        last_event_datetime, sensor_name = get_last_event_datetime(db)
        logger.debug(f"last_event_datetime: {last_event_datetime} sensor_name: {sensor_name}")
        update_no_data(db, last_event_datetime, sensor_name)
        update_high_temp(db, last_event_datetime)
        update_low_temp(db, last_event_datetime)
        check_and_notify(db, now)
    finally:
        db.close()
    logger.info("End")


if __name__ == "__main__":
    run()
