from typing import Optional
import datetime
import decimal

from sqlalchemy import Boolean, DECIMAL, DateTime, String, text
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class NotificationIntervals(Base):
    __tablename__ = 'notification_intervals'

    id: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    interval_minutes: Mapped[int] = mapped_column(INTEGER(11), nullable=False)


class Notifications(Base):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    text_: Mapped[str] = mapped_column('text', String(80), nullable=False)
    value: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(6, 3))
    sensor_name: Mapped[Optional[str]] = mapped_column(String(30))
    last_ok_event: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_ng_event: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_notification: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Sensors(Base):
    __tablename__ = 'sensors'

    print_order: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    sensor_id: Mapped[str] = mapped_column(String(30), nullable=False)
    print_name: Mapped[Optional[str]] = mapped_column(String(30))
    lower_limit: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(6, 3))
    upper_limit: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(6, 3))
    data_check_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('1'))


class Tmprtr(Base):
    __tablename__ = 'tmprtr'

    sensor_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    event_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True, server_default=text('current_timestamp()'))
    tmprtr: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(6, 3))
