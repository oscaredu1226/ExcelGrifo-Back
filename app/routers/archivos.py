from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.conciliacion import ConciliacionDetalleOut, ConciliacionOut
from app.services.conciliacion_service import calculate_stats, save_uploaded_files


router = APIRouter(prefix="/api/conciliaciones", tags=["Archivos"])


@router.post(
    "/{conciliacion_id}/archivos",
    response_model=ConciliacionDetalleOut,
    summary="Subir archivos Excel",
    description="Recibe exactamente dos archivos .xlsx, detecta Izipay y Facturacion, y guarda copias originales.",
    responses={400: {"description": "Archivo invalido"}, 404: {"description": "Conciliacion no encontrada"}, 409: {"description": "Archivos ya existentes"}},
)
def subir_archivos(
    conciliacion_id: int,
    archivos: list[UploadFile] = File(..., description="Dos archivos .xlsx: Izipay y Facturacion."),
    db: Session = Depends(get_db),
):
    conciliacion = save_uploaded_files(db, conciliacion_id, archivos)
    return {
        **ConciliacionOut.model_validate(conciliacion).model_dump(),
        "estadisticas": calculate_stats(db, conciliacion.id),
    }
