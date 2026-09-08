from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.comprobante import ComprobanteOut
from app.schemas.emparejamiento import (
    AutomaticoOut,
    BoletasBatchCreate,
    EmparejamientoCreate,
    EmparejamientoDetalleOut,
    GrupoAmbiguoDetalleOut,
    GrupoAmbiguoOut,
    SugerenciaOut,
)
from app.schemas.izipay import OperacionIzipayOut
from app.services.conciliacion_service import (
    create_boleta_matches,
    create_manual_match,
    delete_match,
    get_ambiguous_group_detail,
    get_ambiguous_groups,
    get_automatic_matches,
    get_pending_records,
    get_suggestions,
)


router = APIRouter(prefix="/api/conciliaciones", tags=["Emparejamientos"])


@router.get(
    "/{conciliacion_id}/automaticos",
    response_model=list[AutomaticoOut],
    summary="Listar automaticos",
    description="Retorna emparejamientos creados automaticamente por monto unico.",
)
def listar_automaticos(conciliacion_id: int, db: Session = Depends(get_db)):
    return get_automatic_matches(db, conciliacion_id)


@router.get(
    "/{conciliacion_id}/ambiguos",
    response_model=list[GrupoAmbiguoOut],
    summary="Listar grupos ambiguos",
    description="Agrupa registros ambiguos por importe, ordenados por facilidad de revision.",
)
def listar_ambiguos(conciliacion_id: int, db: Session = Depends(get_db)):
    return get_ambiguous_groups(db, conciliacion_id)


@router.get(
    "/{conciliacion_id}/ambiguos/{importe}",
    response_model=GrupoAmbiguoDetalleOut,
    summary="Detalle de grupo ambiguo",
    description="Retorna operaciones Izipay y comprobantes pendientes del monto ambiguo solicitado.",
)
def detalle_ambiguo(conciliacion_id: int, importe: str, db: Session = Depends(get_db)):
    return get_ambiguous_group_detail(db, conciliacion_id, importe)


@router.post(
    "/{conciliacion_id}/emparejamientos/boletas",
    response_model=list[OperacionIzipayOut],
    status_code=201,
    summary="Incluir boletas revisadas",
    description="Marca en lote operaciones Izipay como boletas confirmadas por el usuario.",
    responses={400: {"description": "Datos incompatibles"}, 404: {"description": "Registro no encontrado"}, 409: {"description": "Registro ya utilizado"}},
)
def crear_emparejamientos_boleta(conciliacion_id: int, data: BoletasBatchCreate, db: Session = Depends(get_db)):
    return create_boleta_matches(db, conciliacion_id, data)


@router.post(
    "/{conciliacion_id}/emparejamientos",
    response_model=EmparejamientoDetalleOut,
    status_code=201,
    summary="Emparejar manualmente",
    description="Crea una vinculacion manual y la persiste inmediatamente en MySQL.",
    responses={400: {"description": "Datos incompatibles"}, 404: {"description": "Registro no encontrado"}, 409: {"description": "Registro ya utilizado"}},
)
def crear_emparejamiento(conciliacion_id: int, data: EmparejamientoCreate, db: Session = Depends(get_db)):
    return create_manual_match(db, conciliacion_id, data)


@router.delete(
    "/{conciliacion_id}/emparejamientos/{emparejamiento_id}",
    status_code=204,
    summary="Deshacer emparejamiento",
    description="Elimina una vinculacion y devuelve los registros a un estado reutilizable.",
)
def deshacer_emparejamiento(conciliacion_id: int, emparejamiento_id: int, db: Session = Depends(get_db)):
    delete_match(db, conciliacion_id, emparejamiento_id)
    return Response(status_code=204)


@router.get(
    "/{conciliacion_id}/pendientes",
    summary="Obtener pendientes",
    description="Retorna registros abiertos. Permite filtros simples por importe, tipo_documento y estado.",
    response_model=dict[str, list[ComprobanteOut] | list[OperacionIzipayOut]],
)
def obtener_pendientes(
    conciliacion_id: int,
    importe: str | None = Query(default=None),
    tipo_documento: str | None = Query(default=None),
    estado: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_pending_records(db, conciliacion_id, importe, tipo_documento, estado)


@router.get(
    "/{conciliacion_id}/sugerencias",
    response_model=list[SugerenciaOut],
    summary="Obtener sugerencias",
    description="Retorna candidatos auxiliares de montos pequenos, sin conciliarlos automaticamente.",
)
def obtener_sugerencias(conciliacion_id: int, db: Session = Depends(get_db)):
    return get_suggestions(db, conciliacion_id)
