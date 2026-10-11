"""
Cartelera oficial: carga por archivo (admin) y lectura para todos.

``POST /admin/races/upload`` acepta archivos ``.csv``/texto plano Y archivos
de Excel (``.xlsx``, ``.xlsm``, ``.xls``) — estos últimos se leen EN MEMORIA
(``openpyxl``/``xlrd``, ver ``backend/parsers.py``) sin requerir que el admin
los convierta a CSV previamente. En ambos casos se detecta automáticamente
uno de estos dos formatos:

* **Formato A — Reporte oficial INH** (latin-1/cp1252 en CSV, o celdas de
  Excel): bloques ``Carrera Nro: X`` con ``Fecha:`` / ``Hora:`` y tabla de
  ejemplares con columnas ``N°`` y ``Ejemplar`` (alias: ``Nro``, ``Nº``,
  ``Caballo``, ``Nombre``…).
* **Formato B — CSV/Excel plano** (una fila por ejemplar): encabezados
  exactos en la fila 1 — ``numero_carrera``, ``numero_caballo``,
  ``nombre_caballo``, ``fecha``, ``hora`` (se admiten alias en español/inglés
  y variaciones de mayúsculas/minúsculas, ver ``ALIASES`` en
  ``backend/parsers.py``: p. ej. ``carrera``, ``caballo``, ``nombre``,
  ``race_number``, ``horse_name``…).
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import (
    DUEL_ACTIVE,
    OFFICIAL_TOP_N,
    Duel,
    DuelType,
    OfficialResult,
    RaceEntry,
    User,
    get_db,
    official_outcome,
)
from parsers import EXPECTED_HEADER, parse_cartelera
from schemas import OfficialResultsRequest
from security import require_admin
from datetime import datetime, timezone, timedelta

router = APIRouter(tags=["races"])

EXPECTED_HEADER_LABEL = EXPECTED_HEADER


@router.get("/races")
def list_races(db: Session = Depends(get_db)):
    """Cartelera oficial ordenada por carrera y número de caballo."""
    entries = (
        db.query(RaceEntry)
        .order_by(RaceEntry.race_number, RaceEntry.horse_number)
        .all()
    )
    now = datetime.now(timezone.utc)
    result = []
    for e in entries:
        race_dt = e.race_datetime
        if race_dt.tzinfo is None:
            race_dt = race_dt.replace(tzinfo=timezone.utc)
        is_open = now < (race_dt - timedelta(minutes=1))
        d = e.to_dict()
        d["is_open_for_duels"] = is_open
        result.append(d)
    return result


ALLOWED_RACE_EXTENSIONS = (".csv", ".txt", ".xlsx", ".xlsm", ".xls")


@router.post("/admin/races/upload")
async def upload_races(
    file: UploadFile = File(
        ...,
        description=(
            "Reporte INH o CSV plano de la cartelera. Formatos admitidos: "
            ".csv / .txt (texto, UTF-8 o latin-1/cp1252) y Excel .xlsx/.xlsm/.xls "
            "(se leen directamente en memoria, sin conversión previa)."
        ),
    ),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    Procesa el archivo oficial de la cartelera (detección automática de
    formato y de tipo de archivo: texto plano o Excel nativo).

    * **Formato A — Reporte oficial INH** (CSV latin-1/cp1252 o Excel):
      bloques ``Carrera Nro: X`` con ``Fecha:`` / ``Hora:`` y tabla ``N° |
      Ejemplar``.
    * **Formato B — CSV/Excel plano**: encabezados exactos en la fila 1 —
      ``numero_carrera``, ``numero_caballo``, ``nombre_caballo``, ``fecha``,
      ``hora`` (admite alias español/inglés, ver ``backend/parsers.py``).
    * **Tipos de archivo admitidos:** ``.csv``, ``.txt``, ``.xlsx``, ``.xlsm``,
      ``.xls`` (Excel leído nativamente con ``openpyxl``/``xlrd``, sin requerir
      conversión previa a CSV).

    Procesamiento atómico: si hay errores NO se importa nada y se devuelve el
    detalle. Idempotente: si (carrera, caballo) ya existe, actualiza nombre/fecha.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    filename = file.filename or ""
    extension = filename[filename.rfind("."):].lower() if "." in filename else ""
    if extension and extension not in ALLOWED_RACE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tipo de archivo no admitido ({extension}). "
                f"Formatos válidos: {', '.join(ALLOWED_RACE_EXTENSIONS)}."
            ),
        )

    try:
        try:
            parsed = parse_cartelera(raw, filename=filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if parsed.get("errors"):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        f"No se importó ningún ejemplar — {parsed['format_label']} "
                        f"(codificación {parsed['encoding']}). Corrige los errores y reintenta."
                    ),
                    "format": parsed["format"],
                    "errors": parsed["errors"],
                },
            )

        rows = parsed.get("rows", [])
        if not rows:
            raise HTTPException(
                status_code=400,
                detail=(
                    "El archivo no contiene ejemplares válidos — se detectó como "
                    f"{parsed.get('format_label', parsed.get('format'))} "
                    f"(codificación {parsed.get('encoding', '—')}). Verifica que el "
                    "archivo tenga el formato esperado: Formato A (bloques "
                    "'Carrera Nro:'/'Fecha:'/'Hora:' + tabla N°|Ejemplar) o Formato B "
                    f"(encabezado exacto '{EXPECTED_HEADER_LABEL}' en la fila 1 con al "
                    "menos una fila de datos)."
                ),
            )

        imported, updated = 0, 0
        by_race: Dict[int, List[dict]] = {}
        for row in rows:
            existing = (
                db.query(RaceEntry)
                .filter(
                    RaceEntry.race_number == row["race_number"],
                    RaceEntry.horse_number == row["horse_number"],
                )
                .first()
            )
            if existing is not None:
                existing.horse_name = row["horse_name"]
                existing.race_datetime = row["race_datetime"]
                updated += 1
            else:
                db.add(
                    RaceEntry(
                        race_number=row["race_number"],
                        race_datetime=row["race_datetime"],
                        horse_number=row["horse_number"],
                        horse_name=row["horse_name"],
                    )
                )
                imported += 1
            by_race.setdefault(row["race_number"], []).append(row)

        db.commit()

        # Resumen por carrera para mostrar el estado de la importación masiva.
        race_summary = [
            {
                "race_number": race_number,
                "datetime": items[0]["race_datetime"].isoformat(sep=" ", timespec="minutes"),
                "horses": len(items),
            }
            for race_number, items in sorted(by_race.items())
        ]

        return {
            "detail": f"Cartelera procesada correctamente ({parsed['format_label']}).",
            "format": parsed["format"],
            "format_label": parsed["format_label"],
            "encoding": parsed["encoding"],
            "imported": imported,
            "updated": updated,
            "total_rows": len(rows),
            "race_numbers": sorted(by_race.keys()),
            "races": race_summary,
        }

    except HTTPException:
        # Re-lanza validaciones controladas garantizando el rollback de la BD
        db.rollback()
        raise
    except Exception as exc:
        # Atrapa excepciones inesperadas (ej. fallos en el parser o base de datos)
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Error crítico al procesar la estructura del archivo.",
                "format": "ERROR",
                "errors": [f"Detalle técnico: {str(exc)}"],
            },
        )


@router.delete("/admin/races/{entry_id}")
def delete_race_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Elimina una entrada puntual de la cartelera."""
    entry = db.get(RaceEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entrada de cartelera no encontrada.")
    db.delete(entry)
    db.commit()
    return {"detail": "Entrada eliminada.", "id": entry_id}


# ─────────────── Resultados oficiales de llegada (1° al 5°) ───────────────
def _active_duel_preview(db: Session, race_number: int, positions: Dict[int, int]) -> List[dict]:
    """Duelos ACTIVOS de la carrera con la sugerencia calculada contra el marcador."""
    active = (
        db.query(Duel)
        .filter(Duel.race_number == race_number, Duel.status == DUEL_ACTIVE)
        .order_by(Duel.id)
        .all()
    )
    preview = []
    for duel in active:
        duel_type = db.get(DuelType, duel.duel_type_id)
        creator = db.get(User, duel.creator_id)
        acceptor = db.get(User, duel.acceptor_id) if duel.acceptor_id else None
        if positions:
            winner, note = official_outcome(positions, duel.horse_creator, duel.horse_opponent)
        else:
            winner, note = None, "Sin marcador oficial registrado para esta carrera."
        preview.append(
            {
                "duel_id": duel.id,
                "duel_type": duel_type.name if duel_type else "—",
                "logic_rule": duel_type.logic_rule if duel_type else "MANUAL",
                "stake": round(duel.stake or 0.0, 2),
                "pot": round((duel.stake or 0.0) * 2, 2),
                "creator_username": creator.username if creator else "—",
                "acceptor_username": acceptor.username if acceptor else None,
                "horse_creator": duel.horse_creator,
                "horse_creator_name": duel.horse_creator_name,
                "horse_opponent": duel.horse_opponent,
                "horse_opponent_name": duel.horse_opponent_name,
                "suggested_winner_horse": winner,
                "note": note,
                "has_results": bool(positions),
            }
        )
    return preview


def _official_payload(db: Session, race_number: int, rows: List[OfficialResult], detail: str) -> dict:
    positions = {row.horse_number: row.position for row in rows}
    return {
        "detail": detail,
        "race_number": race_number,
        "has_results": bool(rows),
        "top_n": OFFICIAL_TOP_N,
        "results": [row.to_dict() for row in rows],
        "active_duels": _active_duel_preview(db, race_number, positions),
    }


@router.get("/admin/races/{race_number}/official-results")
def get_official_results(
    race_number: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Marcador oficial guardado + previsualización de resolución de duelos ACTIVOS."""
    rows = (
        db.query(OfficialResult)
        .filter(OfficialResult.race_number == race_number)
        .order_by(OfficialResult.position)
        .all()
    )
    entries_count = (
        db.query(RaceEntry).filter(RaceEntry.race_number == race_number).count()
    )
    if not rows and not entries_count:
        raise HTTPException(
            status_code=404,
            detail=f"La carrera {race_number} no existe en la cartelera.",
        )
    return _official_payload(db, race_number, rows, "Marcador oficial consultado.")


@router.post("/admin/races/{race_number}/official-results")
def save_official_results(
    race_number: int,
    payload: OfficialResultsRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Registra (o corrige) el marcador oficial de llegada de la carrera:
    exactamente las 5 posiciones (1° al 5° lugar) identificadas por número de
    caballo. Reemplaza el marcador anterior y devuelve la previsualización para
    resolver los duelos ACTIVOS de esa carrera.

    Regla: todo caballo que no figure en el top 5 queda "fuera del marcador"
    (no clasificado / perdedor).
    """
    entries = db.query(RaceEntry).filter(RaceEntry.race_number == race_number).all()
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=(
                f"La carrera {race_number} no existe en la cartelera. "
                "Carga primero el archivo oficial de ejemplares."
            ),
        )
    horses = {entry.horse_number: entry for entry in entries}

    if len(payload.positions) != OFFICIAL_TOP_N:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren exactamente {OFFICIAL_TOP_N} posiciones (del 1° al 5° lugar).",
        )

    ordered = sorted(payload.positions, key=lambda item: item.position)
    seen_horses, errors = set(), []
    for item in ordered:
        if item.horse_number not in horses:
            errors.append(
                f"El caballo N.º {item.horse_number} no participa en la carrera {race_number}."
            )
            continue
        if item.horse_number in seen_horses:
            errors.append(f"El caballo N.º {item.horse_number} aparece en más de una posición.")
            continue
        seen_horses.add(item.horse_number)

    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "Marcador oficial inválido; no se guardó nada.", "errors": errors},
        )

    # Reemplazo atómico del marcador de la carrera (incluye correcciones).
    db.query(OfficialResult).filter(OfficialResult.race_number == race_number).delete()
    for item in ordered:
        db.add(
            OfficialResult(
                race_number=race_number,
                position=item.position,
                horse_number=item.horse_number,
                horse_name=horses[item.horse_number].horse_name,
                recorded_by=admin.id,
            )
        )
    db.commit()

    rows = (
        db.query(OfficialResult)
        .filter(OfficialResult.race_number == race_number)
        .order_by(OfficialResult.position)
        .all()
    )
    return _official_payload(
        db,
        race_number,
        rows,
        f"Marcador oficial de la carrera {race_number} guardado (1° al 5°).",
    )