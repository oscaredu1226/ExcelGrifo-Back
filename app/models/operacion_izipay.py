from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OperacionIzipay(Base):
    __tablename__ = "operaciones_izipay"
    __table_args__ = (
        Index("ix_operaciones_izipay_conciliacion_importe", "conciliacion_id", "importe"),
        Index("ix_operaciones_izipay_conciliacion_estado", "conciliacion_id", "estado_conciliacion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conciliacion_id: Mapped[int] = mapped_column(ForeignKey("conciliaciones.id"), nullable=False, index=True)
    fila_original: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_transaccion: Mapped[date | None] = mapped_column(Date, nullable=True)
    hora_transaccion: Mapped[time | None] = mapped_column(Time, nullable=True)
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    importe_neto: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    voucher: Mapped[str | None] = mapped_column(String(100), nullable=True)
    codigo_autorizacion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    terminal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_movimiento: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaccion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado_conciliacion: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDIENTE")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    conciliacion = relationship("Conciliacion", back_populates="operaciones_izipay")
    emparejamiento = relationship("Emparejamiento", back_populates="operacion_izipay", uselist=False)
