import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ScannerState(str, enum.Enum):
    offline = "offline"
    waiting = "waiting"
    on_car = "on_car"
    error = "error"


class Scanner(Base):
    __tablename__ = "scanners"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    status: Mapped["ScannerStatus | None"] = relationship(back_populates="scanner", uselist=False)
    owner: Mapped["TelegramUser | None"] = relationship(back_populates="scanner")


class ScannerStatus(Base):
    __tablename__ = "scanner_status"

    scanner_id: Mapped[str] = mapped_column(ForeignKey("scanners.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[ScannerState] = mapped_column(Enum(ScannerState), default=ScannerState.offline)
    bitrate: Mapped[str | None] = mapped_column(String(16))
    vin: Mapped[str | None] = mapped_column(String(32))
    manufacturer: Mapped[str | None] = mapped_column(String(128))
    rpm: Mapped[int | None] = mapped_column()
    speed_kmh: Mapped[int | None] = mapped_column()
    coolant_c: Mapped[int | None] = mapped_column()
    dtc_stored: Mapped[list | None] = mapped_column(JSONB, default=list)
    dtc_pending: Mapped[list | None] = mapped_column(JSONB, default=list)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scanner: Mapped[Scanner] = relationship(back_populates="status")


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    scanner_id: Mapped[str | None] = mapped_column(ForeignKey("scanners.id", ondelete="SET NULL"))
    cursor_key_enc: Mapped[str | None] = mapped_column(Text)
    cursor_key_valid: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scanner: Mapped[Scanner | None] = relationship(back_populates="owner")


class ObdSnapshot(Base):
    """History of OBD reads — base for future analytics / AI context."""

    __tablename__ = "obd_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scanner_id: Mapped[str] = mapped_column(ForeignKey("scanners.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class VehicleWmi(Base):
    """Seed table for future proprietary + standard vehicle DB merge."""

    __tablename__ = "vehicle_wmi"

    wmi: Mapped[str] = mapped_column(String(3), primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column(JSONB)
