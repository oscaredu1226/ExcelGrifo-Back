from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


ESTADOS_CONCILIACION = ("CREADA", "PROCESANDO", "EN_REVISION", "FINALIZADA", "ERROR")


class Conciliacion(Base):
    __tablename__ = "conciliaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    sucursal: Mapped[str] = mapped_column(String(100), nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="CREADA")
    archivo_facturacion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archivo_izipay: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_ultima_modificacion: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    comprobantes = relationship("Comprobante", back_populates="conciliacion", cascade="all, delete-orphan")
    operaciones_izipay = relationship("OperacionIzipay", back_populates="conciliacion", cascade="all, delete-orphan")
    emparejamientos = relationship("Emparejamiento", back_populates="conciliacion", cascade="all, delete-orphan")
