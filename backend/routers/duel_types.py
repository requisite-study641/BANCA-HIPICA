"""Admin — CRUD completo de tipos de duelo y sus reglas lógicas."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import VALID_RULES, Duel, DuelType, get_db
from schemas import DuelTypeCreate, DuelTypeUpdate
from security import require_admin

router = APIRouter(tags=["duel-types"])


def _validate_rule(logic_rule: str) -> str:
    rule = logic_rule.strip().upper()
    if rule not in VALID_RULES:
        raise HTTPException(
            status_code=400,
            detail=f"Regla lógica inválida. Opciones: {', '.join(VALID_RULES)}",
        )
    return rule


# ───────────────────────── Lectura (usuarios y admin) ─────────────────────────
@router.get("/duel-types")
def list_duel_types(db: Session = Depends(get_db)):
    """Catálogo de tipos de duelo (lo usa el formulario de creación de duelos)."""
    types = db.query(DuelType).order_by(DuelType.id).all()
    return [t.to_dict() for t in types]


@router.get("/admin/duel-types/{type_id}")
def get_duel_type(
    type_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    duel_type = db.get(DuelType, type_id)
    if duel_type is None:
        raise HTTPException(status_code=404, detail="Tipo de duelo no encontrado.")
    return duel_type.to_dict()


# ─────────────────────────── Escritura (solo admin) ───────────────────────────
@router.post("/admin/duel-types", status_code=201)
def create_duel_type(
    payload: DuelTypeCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Crea un tipo de duelo con su regla lógica de resolución."""
    duel_type = DuelType(
        name=payload.name.strip(),
        logic_rule=_validate_rule(payload.logic_rule),
        description=payload.description.strip(),
    )
    db.add(duel_type)
    db.commit()
    db.refresh(duel_type)
    return duel_type.to_dict()


@router.put("/admin/duel-types/{type_id}")
def update_duel_type(
    type_id: int,
    payload: DuelTypeUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Modifica nombre, regla lógica y descripción de un tipo de duelo."""
    duel_type = db.get(DuelType, type_id)
    if duel_type is None:
        raise HTTPException(status_code=404, detail="Tipo de duelo no encontrado.")
    duel_type.name = payload.name.strip()
    duel_type.logic_rule = _validate_rule(payload.logic_rule)
    duel_type.description = payload.description.strip()
    db.commit()
    db.refresh(duel_type)
    return duel_type.to_dict()


@router.delete("/admin/duel-types/{type_id}")
def delete_duel_type(
    type_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Elimina un tipo de duelo (bloqueado si ya hay duelos que lo referencian)."""
    duel_type = db.get(DuelType, type_id)
    if duel_type is None:
        raise HTTPException(status_code=404, detail="Tipo de duelo no encontrado.")
    in_use = db.query(Duel).filter(Duel.duel_type_id == type_id).count()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: {in_use} duelo(s) usan este tipo. Modifícalo en su lugar.",
        )
    db.delete(duel_type)
    db.commit()
    return {"detail": "Tipo de duelo eliminado.", "id": type_id}