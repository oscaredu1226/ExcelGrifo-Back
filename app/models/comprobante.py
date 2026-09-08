from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


ESTADOS_REGISTRO = (
    "PENDIENTE",
    "CONCILIADO_AUTOMATICO",
    "CONCILIADO_MANUAL",
    "AMBIGUO",
    "SUGERENCIA",
    "SIN_COINCIDENCIA",
)


class Comprobante(Base):
    __tablename__ = "comprobantes"
    __table_args__ = (
        Index("ix_comprobantes_conciliacion_importe", "conciliacion_id", "importe"),
        Index("ix_comprobantes_conciliacion_estado", "conciliacion_id", "estado_conciliacion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conciliacion_id: Mapped[int] = mapped_column(ForeignKey("conciliaciones.id"), nullable=False, index=True)
    fila_original: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    serie: Mapped[str | None] = mapped_column(String(50), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_pago: Mapped[date | None] = mapped_column(Date, nullable=True)
    documento_cliente: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nombre_cliente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    importe: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    estado_conciliacion: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDIENTE")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    conciliacion = relationship("Conciliacion", back_populates="comprobantes")
    emparejamiento = relationship("Emparejamiento", back_populates="comprobante", uselist=False)
