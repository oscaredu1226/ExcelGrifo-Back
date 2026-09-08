from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ComprobanteOut(BaseModel):
    id: int
    conciliacion_id: int
    fila_original: int
    tipo_documento: str | None = None
    serie: str | None = None
    numero: str | None = None
    fecha_emision: date | None = None
    fecha_pago: date | None = None
    documento_cliente: str | None = None
    nombre_cliente: str | None = None
    importe: Decimal
    estado_conciliacion: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = ConfigDict(from_attributes=True)
