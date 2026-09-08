from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OperacionIzipayOut(BaseModel):
    id: int
    conciliacion_id: int
    fila_original: int
    fecha_transaccion: date | None = None
    hora_transaccion: time | None = None
    importe: Decimal
    importe_neto: Decimal | None = None
    voucher: str | None = None
    codigo_autorizacion: str | None = None
    terminal: str | None = None
    tipo_movimiento: str | None = None
    transaccion: str | None = None
    estado: str | None = None
    estado_conciliacion: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = ConfigDict(from_attributes=True)
