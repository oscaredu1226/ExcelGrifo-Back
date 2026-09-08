from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.conciliacion import ConciliacionCreate, ConciliacionDetalleOut, ConciliacionOut
from app.services.conciliacion_service import (
    calculate_stats,
    create_conciliacion,
    delete_conciliacion,
    get_conciliacion_or_404,
    list_conciliaciones,
    process_conciliacion,
)


router = APIRouter(prefix="/api/conciliaciones", tags=["Conciliaciones"])


def _conciliacion_detalle(conciliacion, db: Session) -> dict:
    return {
        **ConciliacionOut.model_validate(conciliacion).model_dump(),
        "estadisticas": calculate_stats(db, conciliacion.id),
    }


@router.post(
    "",
    response_model=ConciliacionOut,
    status_code=201,
    summary="Crear conciliacion",
    description="Crea una conciliacion vacia para luego subir archivos.",
)
def crear_conciliacion(data: ConciliacionCreate, db: Session = Depends(get_db)):
    return create_conciliacion(db, data)


@router.get(
    "",
    response_model=list[ConciliacionDetalleOut],
    summary="Listar conciliaciones",
    description="Lista las conciliaciones ordenadas por ultima modificacion descendente.",
)
def listar_conciliaciones(db: Session = Depends(get_db)):
    return [_conciliacion_detalle(conciliacion, db) for conciliacion in list_conciliaciones(db)]


@router.delete(
    "/{conciliacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar conciliacion",
    description="Elimina la conciliacion completa, sus registros importados, emparejamientos y archivos cargados.",
    responses={404: {"description": "Conciliacion no encontrada"}},
)
def eliminar_conciliacion(conciliacion_id: int, db: Session = Depends(get_db)):
    delete_conciliacion(db, conciliacion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{conciliacion_id}",
    response_model=ConciliacionDetalleOut,
    summary="Obtener conciliacion",
    description="Obtiene datos generales y estadisticas calculadas desde la base de datos.",
    responses={404: {"description": "Conciliacion no encontrada"}},
)
def obtener_conciliacion(conciliacion_id: int, db: Session = Depends(get_db)):
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    return _conciliacion_detalle(conciliacion, db)


@router.post(
    "/{conciliacion_id}/procesar",
    response_model=ConciliacionDetalleOut,
    summary="Procesar conciliacion",
    description="Importa los Excel originales, concilia montos unicos, marca ambiguos y genera sugerencias.",
    responses={400: {"description": "Error de procesamiento"}, 404: {"description": "Conciliacion no encontrada"}, 409: {"description": "Conciliacion ya procesada"}},
)
def procesar_conciliacion(conciliacion_id: int, db: Session = Depends(get_db)):
    conciliacion = process_conciliacion(db, conciliacion_id)
    return _conciliacion_detalle(conciliacion, db)
