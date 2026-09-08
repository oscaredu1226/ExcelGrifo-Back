from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class ConciliacionCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    sucursal: str = Field(..., min_length=1, max_length=100)
    mes: int = Field(..., ge=1, le=12)
    anio: int = Field(..., ge=2000, le=2100)


class ConciliacionStats(BaseModel):
    total_facturacion: int
    total_izipay: int
    conciliados_automaticos: int
    conciliados_manuales: int
    boletas: int
    grupos_ambiguos: int
    registros_ambiguos: int
    sugerencias: int
    sin_coincidencia: int
    pendientes: int
    porcentaje_progreso: float


class ConciliacionOut(BaseModel):
    id: int
    nombre: str
    sucursal: str
    mes: int
    anio: int
    estado: str
    archivo_facturacion: str | None = None
    archivo_izipay: str | None = None
    fecha_creacion: datetime
    fecha_ultima_modificacion: datetime

    model_config = ConfigDict(from_attributes=True)


class ConciliacionDetalleOut(ConciliacionOut):
    estadisticas: ConciliacionStats
