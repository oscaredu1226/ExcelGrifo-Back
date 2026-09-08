from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app.models import Conciliacion, Comprobante, Emparejamiento, OperacionIzipay
from app.routers import archivos, conciliaciones, emparejamientos, exportacion, health


settings = get_settings()

app = FastAPI(
    title="API Conciliacion Izipay",
    version="1.0.0",
    description="API para conciliacion de operaciones Izipay con comprobantes de facturacion.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health.router)
app.include_router(conciliaciones.router)
app.include_router(archivos.router)
app.include_router(emparejamientos.router)
app.include_router(exportacion.router)
