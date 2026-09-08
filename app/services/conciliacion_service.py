from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from shutil import copyfileobj, rmtree

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.conciliacion import Conciliacion
from app.models.comprobante import Comprobante
from app.models.emparejamiento import Emparejamiento
from app.models.operacion_izipay import OperacionIzipay
from app.services.excel_service import TIPO_FACTURACION, TIPO_IZIPAY, identify_excel_file, read_facturacion, read_izipay, validate_xlsx
from app.utils.money import MONTO_BAJO_MAXIMO, normalize_money


UPLOADS_DIR = Path("uploads")
CONCILIADO_ESTADOS = {"CONCILIADO_AUTOMATICO", "CONCILIADO_MANUAL", "BOLETA"}


def get_conciliacion_or_404(db: Session, conciliacion_id: int) -> Conciliacion:
    conciliacion = db.get(Conciliacion, conciliacion_id)
    if conciliacion is None:
        raise HTTPException(status_code=404, detail="Conciliacion no encontrada.")
    return conciliacion


def touch(conciliacion: Conciliacion) -> None:
    conciliacion.fecha_ultima_modificacion = datetime.utcnow()


def create_conciliacion(db: Session, data) -> Conciliacion:
    conciliacion = Conciliacion(**data.model_dump())
    db.add(conciliacion)
    db.commit()
    db.refresh(conciliacion)
    return conciliacion


def list_conciliaciones(db: Session) -> list[Conciliacion]:
    return list(db.scalars(select(Conciliacion).order_by(Conciliacion.fecha_ultima_modificacion.desc())).all())


def delete_conciliacion(db: Session, conciliacion_id: int) -> None:
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    upload_dir = UPLOADS_DIR / str(conciliacion_id)

    try:
        db.delete(conciliacion)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if upload_dir.exists():
        rmtree(upload_dir, ignore_errors=True)


def save_uploaded_files(db: Session, conciliacion_id: int, files: list[UploadFile]) -> Conciliacion:
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    if len(files) != 2:
        raise HTTPException(status_code=400, detail="Debe subir exactamente dos archivos .xlsx.")

    temp_dir = UPLOADS_DIR / str(conciliacion_id) / "_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    detections = []
    try:
        for index, file in enumerate(files, start=1):
            validate_xlsx(file.filename or "")
            temp_path = temp_dir / f"archivo_{index}.xlsx"
            with temp_path.open("wb") as buffer:
                copyfileobj(file.file, buffer)
            detections.append((file.filename or temp_path.name, temp_path, identify_excel_file(temp_path)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tipos = [detection.tipo for _, _, detection in detections]
    if tipos.count(TIPO_FACTURACION) != 1 or tipos.count(TIPO_IZIPAY) != 1:
        raise HTTPException(
            status_code=400,
            detail="No se pudo identificar uno de los archivos como Izipay o Facturacion.",
        )

    target_dir = UPLOADS_DIR / str(conciliacion_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    facturacion_target = target_dir / "facturacion_original.xlsx"
    izipay_target = target_dir / "izipay_original.xlsx"
    if facturacion_target.exists() or izipay_target.exists():
        raise HTTPException(
            status_code=409,
            detail="La conciliacion ya tiene archivos originales. No se sobrescriben automaticamente.",
        )

    for original_name, temp_path, detection in detections:
        if detection.tipo == TIPO_FACTURACION:
            temp_path.replace(facturacion_target)
            conciliacion.archivo_facturacion = original_name
        else:
            temp_path.replace(izipay_target)
            conciliacion.archivo_izipay = original_name

    touch(conciliacion)
    db.commit()
    db.refresh(conciliacion)
    return conciliacion


def process_conciliacion(db: Session, conciliacion_id: int) -> Conciliacion:
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    existing_comprobantes = db.scalar(select(func.count()).select_from(Comprobante).where(Comprobante.conciliacion_id == conciliacion_id))
    existing_operaciones = db.scalar(select(func.count()).select_from(OperacionIzipay).where(OperacionIzipay.conciliacion_id == conciliacion_id))
    if existing_comprobantes or existing_operaciones:
        raise HTTPException(status_code=409, detail="La conciliacion ya fue procesada.")

    facturacion_path = UPLOADS_DIR / str(conciliacion_id) / "facturacion_original.xlsx"
    izipay_path = UPLOADS_DIR / str(conciliacion_id) / "izipay_original.xlsx"
    if not facturacion_path.exists() or not izipay_path.exists():
        raise HTTPException(status_code=400, detail="Debe subir los archivos originales antes de procesar.")

    conciliacion.estado = "PROCESANDO"
    touch(conciliacion)
    db.commit()

    try:
        comprobantes = [Comprobante(conciliacion_id=conciliacion_id, **row) for row in read_facturacion(facturacion_path)]
        operaciones = [OperacionIzipay(conciliacion_id=conciliacion_id, **row) for row in read_izipay(izipay_path)]
        db.add_all(comprobantes + operaciones)
        db.flush()
        _apply_matching_rules(db, conciliacion_id, comprobantes, operaciones)
        conciliacion.estado = "EN_REVISION"
        touch(conciliacion)
        db.commit()
        db.refresh(conciliacion)
        return conciliacion
    except HTTPException:
        conciliacion.estado = "ERROR"
        touch(conciliacion)
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        conciliacion = get_conciliacion_or_404(db, conciliacion_id)
        conciliacion.estado = "ERROR"
        touch(conciliacion)
        db.commit()
        raise HTTPException(status_code=400, detail=f"No se pudo procesar la conciliacion: {exc}") from exc


def _apply_matching_rules(
    db: Session,
    conciliacion_id: int,
    comprobantes: list[Comprobante],
    operaciones: list[OperacionIzipay],
) -> None:
    facturacion_por_importe: dict[Decimal, list[Comprobante]] = defaultdict(list)
    izipay_por_importe: dict[Decimal, list[OperacionIzipay]] = defaultdict(list)

    for comprobante in comprobantes:
        facturacion_por_importe[comprobante.importe].append(comprobante)
    for operacion in operaciones:
        izipay_por_importe[operacion.importe].append(operacion)

    for importe in set(facturacion_por_importe) | set(izipay_por_importe):
        facturacion = facturacion_por_importe.get(importe, [])
        izipay = izipay_por_importe.get(importe, [])

        if facturacion and izipay and importe <= MONTO_BAJO_MAXIMO:
            for comprobante in facturacion:
                comprobante.estado_conciliacion = "SUGERENCIA"
            for operacion in izipay:
                operacion.estado_conciliacion = "SUGERENCIA"
        elif len(facturacion) == 1 and len(izipay) == 1:
            comprobante = facturacion[0]
            operacion = izipay[0]
            comprobante.estado_conciliacion = "CONCILIADO_AUTOMATICO"
            operacion.estado_conciliacion = "CONCILIADO_AUTOMATICO"
            db.add(
                Emparejamiento(
                    conciliacion_id=conciliacion_id,
                    comprobante_id=comprobante.id,
                    operacion_izipay_id=operacion.id,
                    tipo="AUTOMATICO",
                )
            )
        elif facturacion and izipay:
            estado = "SUGERENCIA" if importe <= MONTO_BAJO_MAXIMO else "AMBIGUO"
            for comprobante in facturacion:
                comprobante.estado_conciliacion = estado
            for operacion in izipay:
                operacion.estado_conciliacion = estado
        else:
            for comprobante in facturacion:
                comprobante.estado_conciliacion = "SIN_COINCIDENCIA"
            for operacion in izipay:
                operacion.estado_conciliacion = "SIN_COINCIDENCIA"


def create_manual_match(db: Session, conciliacion_id: int, data) -> Emparejamiento:
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    try:
        emparejamiento = _build_match(
            db,
            conciliacion_id,
            data.operacion_izipay_id,
            data.comprobante_id,
            "MANUAL",
        )
        db.add(emparejamiento)
        db.flush()
        _recalculate_open_amount_state(db, conciliacion_id, emparejamiento.comprobante.importe)
        touch(conciliacion)
        db.commit()
        db.refresh(emparejamiento)
        return emparejamiento
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def create_boleta_matches(db: Session, conciliacion_id: int, data) -> list[OperacionIzipay]:
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    operacion_ids = data.operaciones_izipay_ids
    if not operacion_ids:
        raise HTTPException(status_code=400, detail="Seleccione al menos una boleta.")
    if len(operacion_ids) > 5000:
        raise HTTPException(status_code=400, detail="Seleccione hasta 5000 boletas por envio.")

    if len(operacion_ids) != len(set(operacion_ids)):
        raise HTTPException(status_code=400, detail="No repita registros en el lote.")

    try:
        operaciones = list(
            db.scalars(
                select(OperacionIzipay).where(
                    OperacionIzipay.conciliacion_id == conciliacion_id,
                    OperacionIzipay.id.in_(operacion_ids),
                )
            ).all()
        )
        if len(operaciones) != len(operacion_ids):
            raise HTTPException(status_code=404, detail="Una o mas operaciones Izipay no existen.")

        importes = {operacion.importe for operacion in operaciones}
        for operacion in operaciones:
            if operacion.estado_conciliacion in CONCILIADO_ESTADOS:
                raise HTTPException(status_code=409, detail="Una o mas operaciones ya estan resueltas.")
            operacion.estado_conciliacion = "BOLETA"

        db.flush()
        for importe in importes:
            _recalculate_open_amount_state(db, conciliacion_id, importe)
        touch(conciliacion)
        db.commit()
        for operacion in operaciones:
            db.refresh(operacion)
        return operaciones
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def _build_match(
    db: Session,
    conciliacion_id: int,
    operacion_izipay_id: int,
    comprobante_id: int,
    tipo: str,
) -> Emparejamiento:
    comprobante = db.get(Comprobante, comprobante_id)
    operacion = db.get(OperacionIzipay, operacion_izipay_id)
    if comprobante is None or operacion is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")
    if comprobante.conciliacion_id != conciliacion_id or operacion.conciliacion_id != conciliacion_id:
        raise HTTPException(status_code=400, detail="Ambos registros deben pertenecer a la misma conciliacion.")
    if comprobante.estado_conciliacion in CONCILIADO_ESTADOS:
        raise HTTPException(status_code=409, detail="El comprobante ya esta conciliado.")
    if operacion.estado_conciliacion in CONCILIADO_ESTADOS:
        raise HTTPException(status_code=409, detail="La operacion Izipay ya esta conciliada.")
    if comprobante.importe != operacion.importe:
        raise HTTPException(status_code=400, detail="Los importes deben coincidir exactamente.")

    existing = db.scalar(
        select(Emparejamiento).where(
            Emparejamiento.conciliacion_id == conciliacion_id,
            (
                (Emparejamiento.comprobante_id == comprobante.id)
                | (Emparejamiento.operacion_izipay_id == operacion.id)
            ),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Uno de los registros ya fue utilizado.")

    emparejamiento = Emparejamiento(
        conciliacion_id=conciliacion_id,
        comprobante_id=comprobante.id,
        operacion_izipay_id=operacion.id,
        tipo=tipo,
    )
    emparejamiento.comprobante = comprobante
    emparejamiento.operacion_izipay = operacion
    comprobante.estado_conciliacion = "CONCILIADO_MANUAL"
    operacion.estado_conciliacion = "CONCILIADO_MANUAL"
    return emparejamiento


def delete_match(db: Session, conciliacion_id: int, emparejamiento_id: int) -> None:
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)
    emparejamiento = db.scalar(
        select(Emparejamiento)
        .where(Emparejamiento.id == emparejamiento_id, Emparejamiento.conciliacion_id == conciliacion_id)
        .options(joinedload(Emparejamiento.comprobante), joinedload(Emparejamiento.operacion_izipay))
    )
    if emparejamiento is None:
        raise HTTPException(status_code=404, detail="Emparejamiento no encontrado.")

    importe = emparejamiento.comprobante.importe
    emparejamiento.comprobante.estado_conciliacion = "PENDIENTE"
    emparejamiento.operacion_izipay.estado_conciliacion = "PENDIENTE"
    db.delete(emparejamiento)
    db.flush()
    _recalculate_open_amount_state(db, conciliacion_id, importe)
    touch(conciliacion)
    db.commit()


def _recalculate_open_amount_state(db: Session, conciliacion_id: int, importe: Decimal) -> None:
    comprobantes = list(
        db.scalars(
            select(Comprobante).where(
                Comprobante.conciliacion_id == conciliacion_id,
                Comprobante.importe == importe,
                Comprobante.estado_conciliacion.not_in(CONCILIADO_ESTADOS),
            )
        ).all()
    )
    operaciones = list(
        db.scalars(
            select(OperacionIzipay).where(
                OperacionIzipay.conciliacion_id == conciliacion_id,
                OperacionIzipay.importe == importe,
                OperacionIzipay.estado_conciliacion.not_in(CONCILIADO_ESTADOS),
            )
        ).all()
    )
    if not comprobantes or not operaciones:
        estado = "SIN_COINCIDENCIA"
    elif importe <= MONTO_BAJO_MAXIMO:
        estado = "SUGERENCIA"
    elif len(comprobantes) > 1 or len(operaciones) > 1:
        estado = "AMBIGUO"
    else:
        estado = "PENDIENTE"

    for comprobante in comprobantes:
        comprobante.estado_conciliacion = estado
    for operacion in operaciones:
        operacion.estado_conciliacion = estado


def calculate_stats(db: Session, conciliacion_id: int) -> dict:
    _normalize_unmatchable_open_states(db, conciliacion_id)
    conciliacion = get_conciliacion_or_404(db, conciliacion_id)

    total_facturacion = db.scalar(select(func.count()).select_from(Comprobante).where(Comprobante.conciliacion_id == conciliacion_id)) or 0
    total_izipay = db.scalar(select(func.count()).select_from(OperacionIzipay).where(OperacionIzipay.conciliacion_id == conciliacion_id)) or 0
    if total_facturacion == 0 and total_izipay == 0:
        preview_stats = _calculate_uploaded_file_stats(conciliacion)
        if preview_stats is not None:
            return preview_stats

    automaticos = db.scalar(select(func.count()).select_from(Emparejamiento).where(Emparejamiento.conciliacion_id == conciliacion_id, Emparejamiento.tipo == "AUTOMATICO")) or 0
    manuales = db.scalar(select(func.count()).select_from(Emparejamiento).where(Emparejamiento.conciliacion_id == conciliacion_id, Emparejamiento.tipo.in_(("MANUAL", "BOLETA")))) or 0
    boletas = db.scalar(select(func.count()).select_from(OperacionIzipay).where(OperacionIzipay.conciliacion_id == conciliacion_id, OperacionIzipay.estado_conciliacion == "BOLETA")) or 0
    registros_ambiguos = _count_records_by_state(db, conciliacion_id, "AMBIGUO")
    sugerencias = _count_records_by_state(db, conciliacion_id, "SUGERENCIA")
    sin_coincidencia = _count_records_by_state(db, conciliacion_id, "SIN_COINCIDENCIA")
    pendientes_sin_clasificar = _count_records_by_state(db, conciliacion_id, "PENDIENTE")
    pendientes = pendientes_sin_clasificar + registros_ambiguos + sugerencias + sin_coincidencia
    grupos_ambiguos = len(get_ambiguous_groups(db, conciliacion_id))
    total_registros = total_facturacion + total_izipay
    progreso = (((automaticos + manuales) * 2 + boletas) / total_registros * 100) if total_registros else 0

    return {
        "total_facturacion": total_facturacion,
        "total_izipay": total_izipay,
        "conciliados_automaticos": automaticos,
        "conciliados_manuales": manuales,
        "boletas": boletas,
        "grupos_ambiguos": grupos_ambiguos,
        "registros_ambiguos": registros_ambiguos,
        "sugerencias": sugerencias,
        "sin_coincidencia": sin_coincidencia,
        "pendientes": pendientes,
        "porcentaje_progreso": round(progreso, 2),
    }


def _calculate_uploaded_file_stats(conciliacion: Conciliacion) -> dict | None:
    facturacion_path = UPLOADS_DIR / str(conciliacion.id) / "facturacion_original.xlsx"
    izipay_path = UPLOADS_DIR / str(conciliacion.id) / "izipay_original.xlsx"
    if not facturacion_path.exists() or not izipay_path.exists():
        return None

    try:
        total_facturacion = len(read_facturacion(facturacion_path))
        total_izipay = len(read_izipay(izipay_path))
    except Exception:
        return None

    return {
        "total_facturacion": total_facturacion,
        "total_izipay": total_izipay,
        "conciliados_automaticos": 0,
        "conciliados_manuales": 0,
        "boletas": 0,
        "grupos_ambiguos": 0,
        "registros_ambiguos": 0,
        "sugerencias": 0,
        "sin_coincidencia": 0,
        "pendientes": total_facturacion + total_izipay,
        "porcentaje_progreso": 0,
    }


def _count_records_by_state(db: Session, conciliacion_id: int, estado: str) -> int:
    comprobantes = db.scalar(
        select(func.count()).select_from(Comprobante).where(
            Comprobante.conciliacion_id == conciliacion_id,
            Comprobante.estado_conciliacion == estado,
        )
    ) or 0
    operaciones = db.scalar(
        select(func.count()).select_from(OperacionIzipay).where(
            OperacionIzipay.conciliacion_id == conciliacion_id,
            OperacionIzipay.estado_conciliacion == estado,
        )
    ) or 0
    return comprobantes + operaciones


def get_automatic_matches(db: Session, conciliacion_id: int) -> list[dict]:
    get_conciliacion_or_404(db, conciliacion_id)
    rows = db.scalars(
        select(Emparejamiento)
        .where(Emparejamiento.conciliacion_id == conciliacion_id, Emparejamiento.tipo == "AUTOMATICO")
        .options(joinedload(Emparejamiento.comprobante), joinedload(Emparejamiento.operacion_izipay))
        .order_by(Emparejamiento.id)
    ).all()
    return [
        {
            "emparejamiento_id": item.id,
            "comprobante_id": item.comprobante_id,
            "fila_facturacion": item.comprobante.fila_original,
            "tipo_documento": item.comprobante.tipo_documento,
            "serie": item.comprobante.serie,
            "numero": item.comprobante.numero,
            "importe": item.comprobante.importe,
            "operacion_izipay_id": item.operacion_izipay_id,
            "fila_izipay": item.operacion_izipay.fila_original,
            "fecha_transaccion": item.operacion_izipay.fecha_transaccion.isoformat() if item.operacion_izipay.fecha_transaccion else None,
            "voucher": item.operacion_izipay.voucher,
        }
        for item in rows
    ]


def get_ambiguous_groups(db: Session, conciliacion_id: int) -> list[dict]:
    get_conciliacion_or_404(db, conciliacion_id)
    _normalize_unmatchable_open_states(db, conciliacion_id)
    facturacion = _group_amounts(db, Comprobante, conciliacion_id, "AMBIGUO")
    izipay = _group_amounts(db, OperacionIzipay, conciliacion_id, "AMBIGUO")
    groups = []
    for importe in set(facturacion) & set(izipay):
        groups.append(
            {
                "importe": importe,
                "cantidad_izipay": izipay.get(importe, 0),
                "cantidad_facturacion": facturacion.get(importe, 0),
                "pendientes_izipay": izipay.get(importe, 0),
                "pendientes_facturacion": facturacion.get(importe, 0),
            }
        )
    return sorted(groups, key=lambda item: (item["cantidad_izipay"] + item["cantidad_facturacion"], abs(item["cantidad_izipay"] - item["cantidad_facturacion"])))


def _normalize_unmatchable_open_states(db: Session, conciliacion_id: int) -> None:
    changed = False

    for estado in ("AMBIGUO", "SUGERENCIA"):
        facturacion = _group_amounts(db, Comprobante, conciliacion_id, estado)
        izipay = _group_amounts(db, OperacionIzipay, conciliacion_id, estado)
        facturacion_sin_pareja = set(facturacion) - set(izipay)
        izipay_sin_pareja = set(izipay) - set(facturacion)

        if facturacion_sin_pareja:
            comprobantes = db.scalars(
                select(Comprobante).where(
                    Comprobante.conciliacion_id == conciliacion_id,
                    Comprobante.estado_conciliacion == estado,
                    Comprobante.importe.in_(list(facturacion_sin_pareja)),
                )
            ).all()
            for comprobante in comprobantes:
                comprobante.estado_conciliacion = "SIN_COINCIDENCIA"
                changed = True

        if izipay_sin_pareja:
            operaciones = db.scalars(
                select(OperacionIzipay).where(
                    OperacionIzipay.conciliacion_id == conciliacion_id,
                    OperacionIzipay.estado_conciliacion == estado,
                    OperacionIzipay.importe.in_(list(izipay_sin_pareja)),
                )
            ).all()
            for operacion in operaciones:
                operacion.estado_conciliacion = "SIN_COINCIDENCIA"
                changed = True

    if changed:
        conciliacion = db.get(Conciliacion, conciliacion_id)
        if conciliacion is not None:
            touch(conciliacion)
        db.commit()


def _group_amounts(db: Session, model, conciliacion_id: int, estado: str) -> dict[Decimal, int]:
    rows = db.execute(
        select(model.importe, func.count())
        .where(model.conciliacion_id == conciliacion_id, model.estado_conciliacion == estado)
        .group_by(model.importe)
    ).all()
    return {importe: count for importe, count in rows}


def get_ambiguous_group_detail(db: Session, conciliacion_id: int, importe_text: str) -> dict:
    get_conciliacion_or_404(db, conciliacion_id)
    importe = normalize_money(importe_text)
    if importe is None:
        raise HTTPException(status_code=400, detail="Importe incorrecto.")
    operaciones = list(
        db.scalars(
            select(OperacionIzipay).where(
                OperacionIzipay.conciliacion_id == conciliacion_id,
                OperacionIzipay.importe == importe,
                OperacionIzipay.estado_conciliacion == "AMBIGUO",
            )
        ).all()
    )
    comprobantes = list(
        db.scalars(
            select(Comprobante).where(
                Comprobante.conciliacion_id == conciliacion_id,
                Comprobante.importe == importe,
                Comprobante.estado_conciliacion == "AMBIGUO",
            )
        ).all()
    )
    return {"importe": importe, "izipay": operaciones, "facturacion": comprobantes}


def get_pending_records(db: Session, conciliacion_id: int, importe: str | None, tipo_documento: str | None, estado: str | None) -> dict:
    get_conciliacion_or_404(db, conciliacion_id)
    importe_decimal = normalize_money(importe) if importe else None
    if importe and importe_decimal is None:
        raise HTTPException(status_code=400, detail="Importe incorrecto.")

    comprobantes_query = select(Comprobante).where(Comprobante.conciliacion_id == conciliacion_id)
    operaciones_query = select(OperacionIzipay).where(OperacionIzipay.conciliacion_id == conciliacion_id)
    if importe_decimal is not None:
        comprobantes_query = comprobantes_query.where(Comprobante.importe == importe_decimal)
        operaciones_query = operaciones_query.where(OperacionIzipay.importe == importe_decimal)
    if tipo_documento:
        comprobantes_query = comprobantes_query.where(Comprobante.tipo_documento == tipo_documento)
    if estado:
        comprobantes_query = comprobantes_query.where(Comprobante.estado_conciliacion == estado)
        operaciones_query = operaciones_query.where(OperacionIzipay.estado_conciliacion == estado)
    else:
        abiertos = {"PENDIENTE", "AMBIGUO", "SUGERENCIA", "SIN_COINCIDENCIA"}
        comprobantes_query = comprobantes_query.where(Comprobante.estado_conciliacion.in_(abiertos))
        operaciones_query = operaciones_query.where(OperacionIzipay.estado_conciliacion.in_(abiertos))

    return {
        "facturacion": list(db.scalars(comprobantes_query.order_by(Comprobante.importe, Comprobante.fila_original)).all()),
        "izipay": list(db.scalars(operaciones_query.order_by(OperacionIzipay.importe, OperacionIzipay.fila_original)).all()),
    }


def get_suggestions(db: Session, conciliacion_id: int) -> list[dict]:
    get_conciliacion_or_404(db, conciliacion_id)
    facturacion = _group_amounts(db, Comprobante, conciliacion_id, "SUGERENCIA")
    izipay = _group_amounts(db, OperacionIzipay, conciliacion_id, "SUGERENCIA")
    suggestions = []
    for importe in sorted(set(facturacion) & set(izipay)):
        operaciones = list(
            db.scalars(
                select(OperacionIzipay).where(
                    OperacionIzipay.conciliacion_id == conciliacion_id,
                    OperacionIzipay.importe == importe,
                    OperacionIzipay.estado_conciliacion == "SUGERENCIA",
                )
            ).all()
        )
        comprobantes = list(
            db.scalars(
                select(Comprobante).where(
                    Comprobante.conciliacion_id == conciliacion_id,
                    Comprobante.importe == importe,
                    Comprobante.estado_conciliacion == "SUGERENCIA",
                )
                .order_by((Comprobante.tipo_documento == "03").desc(), Comprobante.fecha_pago)
            ).all()
        )
        suggestions.append(
            {
                "importe": importe,
                "motivo": "Monto pequeno ambiguo. Es solo una sugerencia; no se concilia automaticamente.",
                "prioridad": "Boletas primero y fechas cercanas solo para ordenar revision.",
                "izipay": operaciones,
                "facturacion": comprobantes,
            }
        )
    return suggestions
