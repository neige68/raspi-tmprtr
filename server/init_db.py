"""DB初期化スクリプト: テーブル作成 + 初期データ投入"""
from database import SessionLocal, engine
from models import Base, NotificationIntervals, Notifications


def init():
    Base.metadata.create_all(bind=engine)
    print("テーブル作成完了")

    db = SessionLocal()
    try:
        if db.query(NotificationIntervals).count() == 0:
            db.add(NotificationIntervals(id=1, interval_minutes=60))
            print("notification_intervals: 初期データ投入（60分）")

        if db.query(Notifications).count() == 0:
            db.add_all([
                Notifications(id=1, text_='No Data'),
                Notifications(id=2, text_='高温'),
                Notifications(id=3, text_='低温'),
            ])
            print("notifications: 初期データ投入（3件）")

        db.commit()
    finally:
        db.close()

    print("初期化完了")


if __name__ == '__main__':
    init()
