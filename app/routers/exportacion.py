from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.exportacion_service import export_conciliacion


router = APIRouter(prefix="/api/conciliaciones", tags=["Exportacion"])


@router.get(
    "/{conciliacion_id}/exportar",
    summary="Exportar archivos con match",
    description="Genera un ZIP con dos Excel: Facturacion e Izipay, ambos con columnas de match, sin modificar los originales.",
    responses={200: {"description": "Archivo ZIP generado"}, 400: {"description": "No existen archivos originales"}, 404: {"description": "Conciliacion no encontrada"}},
)
def exportar_conciliacion(conciliacion_id: int, db: Session = Depends(get_db)):
    path = export_conciliacion(db, conciliacion_id)
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/zip",
    )
