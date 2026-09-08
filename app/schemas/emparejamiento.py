from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.comprobante import ComprobanteOut
from app.schemas.izipay import OperacionIzipayOut


class EmparejamientoCreate(BaseModel):
    operacion_izipay_id: int
    comprobante_id: int


class BoletasBatchCreate(BaseModel):
    operaciones_izipay_ids: list[int]


class EmparejamientoOut(BaseModel):
    id: int
    conciliacion_id: int
    comprobante_id: int
    operacion_izipay_id: int
    tipo: str
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)


class EmparejamientoDetalleOut(EmparejamientoOut):
    comprobante: ComprobanteOut
    operacion_izipay: OperacionIzipayOut


class AutomaticoOut(BaseModel):
    emparejamiento_id: int
    comprobante_id: int
    fila_facturacion: int
    tipo_documento: str | None = None
    serie: str | None = None
    numero: str | None = None
    importe: Decimal
    operacion_izipay_id: int
    fila_izipay: int
    fecha_transaccion: str | None = None
    voucher: str | None = None


class GrupoAmbiguoOut(BaseModel):
    importe: Decimal
    cantidad_izipay: int
    cantidad_facturacion: int
    pendientes_izipay: int
    pendientes_facturacion: int


class GrupoAmbiguoDetalleOut(BaseModel):
    importe: Decimal
    izipay: list[OperacionIzipayOut]
    facturacion: list[ComprobanteOut]


class SugerenciaOut(BaseModel):
    importe: Decimal
    motivo: str
    prioridad: str
    izipay: list[OperacionIzipayOut]
    facturacion: list[ComprobanteOut]
