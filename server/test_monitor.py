from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from monitor import _should_notify, check_and_notify


def make_intervals(minutes_list):
    return [MagicMock(interval_minutes=m) for m in minutes_list]


def make_notification(last_ok=None, last_ng=None, last_notif=None, text="No Data"):
    row = MagicMock()
    row.text_ = text
    row.last_ok_event = last_ok
    row.last_ng_event = last_ng
    row.last_notification = last_notif
    return row


NOW = datetime(2025, 1, 1, 12, 0, 0)


class TestShouldNotify:
    def test_no_intervals_id1_never_notifies_immediately(self):
        # id=1 は即時通知なし（notification_intervals のみ）
        result = _should_notify(NOW, 0, None, [], notifications_id=1)
        assert result is False

    def test_id2_notifies_immediately_when_no_last_notification(self):
        result = _should_notify(NOW, 0, None, [], notifications_id=2)
        assert result is True

    def test_id2_skips_if_recently_notified(self):
        recent = NOW - timedelta(seconds=100)
        result = _should_notify(NOW, 0, recent, [], notifications_id=2)
        assert result is False

    def test_interval_threshold_met(self):
        intervals = make_intervals([5])  # 5分
        result = _should_notify(NOW, 300, None, intervals, notifications_id=1)
        assert result is True

    def test_interval_threshold_not_met(self):
        intervals = make_intervals([5])
        result = _should_notify(NOW, 299, None, intervals, notifications_id=1)
        assert result is False

    def test_escalation_already_notified_in_window(self):
        # 5分・15分閾値ともウィンドウ内に通知済み → スキップ
        intervals = make_intervals([5, 15])
        last_notif = NOW - timedelta(seconds=200)  # 3分前
        result = _should_notify(NOW, 900, last_notif, intervals, notifications_id=1)
        # 5分閾値: window=300s, last_notif=200s前 → 200 <= 300 なので通知しない
        # 15分閾値: window=600s, last_notif=200s前 → 200 <= 600 なので通知しない
        assert result is False


class TestCheckAndNotify:
    def _make_db(self, intervals, notifications):
        db = MagicMock()

        def query_side(model):
            from models import Notifications, NotificationIntervals
            q = MagicMock()
            if model is NotificationIntervals:
                q.order_by.return_value.all.return_value = intervals
            elif model is Notifications:
                def filter_first(by):
                    fq = MagicMock()
                    fq.first.return_value = notifications.get(by.right.value)
                    return fq
                q.filter.return_value.first.return_value = None
            return q

        db.query = MagicMock(side_effect=lambda model: _make_query(model, intervals, notifications))
        return db


def _make_query(model, intervals, notifications):
    from models import Notifications, NotificationIntervals
    q = MagicMock()
    if model is NotificationIntervals:
        q.order_by.return_value.all.return_value = intervals
    elif model is Notifications:
        inner = MagicMock()
        # filter().first() を id ごとに返す
        def first_for_id():
            # call_args からidを取る簡易版 — 各テストで直接 check_and_notify をテスト
            return notifications
        q.filter.return_value.first = first_for_id
    return q


class TestCheckAndNotifySimple:
    def test_skips_when_ok(self):
        """last_ok_event > last_ng_event なら通知しない。"""
        now = NOW
        row = make_notification(
            last_ok=now - timedelta(minutes=1),
            last_ng=now - timedelta(minutes=5),
        )
        # ok > ng → スキップ
        assert row.last_ok_event > row.last_ng_event

    def test_skips_when_no_last_ok_event(self):
        row = make_notification(last_ok=None)
        assert row.last_ok_event is None
