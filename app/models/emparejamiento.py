from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


TIPOS_EMPAREJAMIENTO = ("AUTOMATICO", "MANUAL", "BOLETA")


class Emparejamiento(Base):
    __tablename__ = "emparejamientos"
    __table_args__ = (
        UniqueConstraint("comprobante_id", name="uq_emparejamientos_comprobante"),
        UniqueConstraint("operacion_izipay_id", name="uq_emparejamientos_operacion_izipay"),
        UniqueConstraint(
            "conciliacion_id",
            "comprobante_id",
            "operacion_izipay_id",
            name="uq_emparejamientos_conciliacion_par",
        ),
        Index("ix_emparejamientos_conciliacion_tipo", "conciliacion_id", "tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conciliacion_id: Mapped[int] = mapped_column(ForeignKey("conciliaciones.id"), nullable=False, index=True)
    comprobante_id: Mapped[int] = mapped_column(ForeignKey("comprobantes.id"), nullable=False)
    operacion_izipay_id: Mapped[int] = mapped_column(ForeignKey("operaciones_izipay.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    conciliacion = relationship("Conciliacion", back_populates="emparejamientos")
    comprobante = relationship("Comprobante", back_populates="emparejamiento")
    operacion_izipay = relationship("OperacionIzipay", back_populates="emparejamiento")
