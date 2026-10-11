"""
Banca Hípica P2P — Capa de datos (SQLite + SQLAlchemy).

Define las constantes de negocio (comisión del 5%, estados de duelo y reglas
lógicas), el modelo de tablas y el seed inicial (usuario administrador,
tipos de duelo por defecto y la fila de datos bancarios).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    Boolean,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ────────────────────────── Constantes de negocio ──────────────────────────
FEE_PERCENTAGE = 0.05  # 5% de comisión fija para la casa (la administración).

ROLE_ADMIN = "admin"
ROLE_USER = "user"

DUEL_OPEN = "OPEN"        # Publicado, esperando oponente. Escrow = stake del creador.
DUEL_ACTIVE = "ACTIVE"    # Aceptado por el oponente. Escrow = stake x 2 (pozo completo).
DUEL_RESOLVED = "RESOLVED"  # Resuelto por la administración (pago o reembolso ejecutados).

REQ_PENDING = "PENDING"
REQ_APPROVED = "APPROVED"
REQ_REJECTED = "REJECTED"
REQ_PAID = "PAID"

# Reglas lógicas soportadas en duel_types.logic_rule:
RULE_LOWEST = "LOWEST_HORSE_NUMBER"    # Gana el caballo de MENOR número.
RULE_HIGHEST = "HIGHEST_HORSE_NUMBER"  # Gana el caballo de MAYOR número.
RULE_MANUAL = "MANUAL"                 # El admin ingresa el caballo ganador oficial.
RULE_TIE = "TIE_REFUND"                # Empate declarado: reembolso total, sin comisión.
RULE_OFFICIAL = "OFFICIAL_FINISH"      # Gana quien mejores posiciones tenga en el marcador (top 5).
VALID_RULES = (RULE_LOWEST, RULE_HIGHEST, RULE_MANUAL, RULE_TIE, RULE_OFFICIAL)

# Marcador oficial de llegada: puestos almacenados por carrera (1.º … 5.º).
OFFICIAL_TOP_N = 5

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# ───────────────────────────── Motor / Sesión ─────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)
Base = declarative_base()


def get_db():
    """Dependencia FastAPI: una sesión de base de datos por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────── Modelos ────────────────────────────────
class User(Base):
    """users — comunidad y administración."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(160), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    role = Column(String(16), nullable=False, default=ROLE_USER)  # 'admin' | 'user'
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "balance": round(self.balance or 0.0, 2),
            "role": self.role,
        }


class AuthToken(Base):
    """auth_tokens — sesiones móviles mediante token Bearer."""

    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BankInfo(Base):
    """bank_info — datos bancarios centralizados del administrador (fila única)."""

    __tablename__ = "bank_info"

    id = Column(Integer, primary_key=True)
    bank_name = Column(String(120), nullable=False, default="")
    phone = Column(String(40), nullable=False, default="")        # Teléfono / wallet móvil
    id_number = Column(String(40), nullable=False, default="")    # Cédula
    account_type = Column(String(40), nullable=False, default="") # Ahorro / Corriente / etc.
    holder_name = Column(String(120), nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "bank_name": self.bank_name,
            "phone": self.phone,
            "id_number": self.id_number,
            "account_type": self.account_type,
            "holder_name": self.holder_name,
        }


class RaceEntry(Base):
    """race_entries — cartelera oficial cargada por archivo desde el admin."""

    __tablename__ = "race_entries"

    id = Column(Integer, primary_key=True)
    race_number = Column(Integer, nullable=False, index=True)
    race_datetime = Column(DateTime, nullable=False)
    horse_number = Column(Integer, nullable=False, index=True)
    horse_name = Column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint("race_number", "horse_number", name="uq_race_horse"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "race_number": self.race_number,
            "race_datetime": self.race_datetime.isoformat(sep=" ", timespec="minutes")
            if self.race_datetime else None,
            "horse_number": self.horse_number,
            "horse_name": self.horse_name,
        }


class OfficialResult(Base):
    """official_results — marcador oficial de llegada por carrera (1° al 5° lugar)."""

    __tablename__ = "official_results"

    id = Column(Integer, primary_key=True)
    race_number = Column(Integer, nullable=False, index=True)
    position = Column(Integer, nullable=False)     # 1 … OFFICIAL_TOP_N (5)
    horse_number = Column(Integer, nullable=False)
    horse_name = Column(String(120), nullable=False, default="")
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("race_number", "horse_number", name="uq_official_race_horse"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "race_number": self.race_number,
            "position": self.position,
            "horse_number": self.horse_number,
            "horse_name": self.horse_name,
            "created_at": self.created_at.isoformat(sep=" ", timespec="seconds")
            if self.created_at else None,
        }


class DuelType(Base):
    """duel_types — catálogo gestionado EXCLUSIVAMENTE por el administrador."""

    __tablename__ = "duel_types"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    logic_rule = Column(String(60), nullable=False)
    description = Column(Text, nullable=False, default="")
    is_matchup = Column(Boolean, nullable=False, default=False)  # MARCAS
    is_morocha = Column(Boolean, nullable=False, default=False)  # MOROCHA

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "logic_rule": self.logic_rule,
            "description": self.description or "",
            "is_matchup": self.is_matchup,
            "is_morocha": self.is_morocha,
        }


class Duel(Base):
    """duels — apuestas P2P con escrow y comisión del 5% para la casa."""

    __tablename__ = "duels"

    id = Column(Integer, primary_key=True)
    duel_type_id = Column(Integer, ForeignKey("duel_types.id"), nullable=False, index=True)

    race_number = Column(Integer, nullable=False, index=True)
    race_datetime = Column(DateTime, nullable=False)

    # Selección de caballos
    horse_creator = Column(Integer, nullable=False)
    horse_opponent = Column(Integer, nullable=False)
    horse_creator_name = Column(String(120), nullable=False, default="")
    horse_opponent_name = Column(String(120), nullable=False, default="")

    # Segundos caballos para MOROCHA
    horse_creator_2 = Column(Integer, nullable=True)
    horse_opponent_2 = Column(Integer, nullable=True)
    horse_creator_2_name = Column(String(120), nullable=True, default="")
    horse_opponent_2_name = Column(String(120), nullable=True, default="")

    horse_acceptor = Column(Integer, nullable=True)

    stake = Column(Float, nullable=False)
    fee_percentage = Column(Float, nullable=False, default=FEE_PERCENTAGE)

    status = Column(String(16), nullable=False, default=DUEL_OPEN, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    acceptor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    winner_horse_number = Column(Integer, nullable=True)
    commission_amount = Column(Float, nullable=True)
    payout_amount = Column(Float, nullable=True)
    resolution_note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "duel_type_id": self.duel_type_id,
            "race_number": self.race_number,
            "race_datetime": self.race_datetime.isoformat(sep=" ", timespec="minutes")
            if self.race_datetime else None,
            "horse_creator": self.horse_creator,
            "horse_creator_name": self.horse_creator_name,
            "horse_opponent": self.horse_opponent,
            "horse_opponent_name": self.horse_opponent_name,
            "horse_creator_2": self.horse_creator_2,
            "horse_creator_2_name": self.horse_creator_2_name,
            "horse_opponent_2": self.horse_opponent_2,
            "horse_opponent_2_name": self.horse_opponent_2_name,
            "horse_acceptor": self.horse_acceptor,
            "stake": round(self.stake or 0.0, 2),
            "fee_percentage": self.fee_percentage,
            "status": self.status,
            "creator_id": self.creator_id,
            "acceptor_id": self.acceptor_id,
            "winner_id": self.winner_id,
            "winner_horse_number": self.winner_horse_number,
            "commission_amount": round(self.commission_amount, 2)
            if self.commission_amount is not None else None,
            "payout_amount": round(self.payout_amount, 2)
            if self.payout_amount is not None else None,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(sep=" ", timespec="seconds")
            if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat(sep=" ", timespec="seconds")
            if self.accepted_at else None,
            "resolved_at": self.resolved_at.isoformat(sep=" ", timespec="seconds")
            if self.resolved_at else None,
        }


class TopUpRequest(Base):
    """top_up_requests — recargas por pago móvil reportadas por el usuario."""

    __tablename__ = "top_up_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reference = Column(String(80), nullable=False)
    wallet_phone = Column(String(40), nullable=False)
    status = Column(String(16), nullable=False, default=REQ_PENDING, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": round(self.amount or 0.0, 2),
            "reference": self.reference,
            "wallet_phone": self.wallet_phone,
            "status": self.status,
            "created_at": self.created_at.isoformat(sep=" ", timespec="seconds")
            if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat(sep=" ", timespec="seconds")
            if self.reviewed_at else None,
            "note": self.note,
        }


class WithdrawalRequest(Base):
    """withdrawal_requests — retiros procesados por el administrador."""

    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    destination_phone = Column(String(40), nullable=False)
    status = Column(String(16), nullable=False, default=REQ_PENDING, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": round(self.amount or 0.0, 2),
            "destination_phone": self.destination_phone,
            "status": self.status,
            "created_at": self.created_at.isoformat(sep=" ", timespec="seconds")
            if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat(sep=" ", timespec="seconds")
            if self.reviewed_at else None,
            "note": self.note,
        }


# ─────────────────── Marcador oficial: utilidades de negocio ───────────────────
def get_official_positions(db, race_number: int) -> Dict[int, int]:
    """{número de caballo: posición 1-5} de la carrera; {} si no hay marcador."""
    rows = db.query(OfficialResult).filter(OfficialResult.race_number == race_number).all()
    return {row.horse_number: row.position for row in rows}


def official_outcome(
    positions: Dict[int, int], horse_a: int, horse_b: int
) -> Tuple[Optional[int], str]:
    """
    Compara dos ejemplares contra el marcador oficial (top 5).

    Reglas:
      * Caballo dentro del top 5 → su posición cuenta (mejor posición gana).
      * Caballo fuera del top 5 → "fuera del marcador" = perdedor.
      * Ambos fuera del top 5 → sin ganador (devuelve None ⇒ reembolso).

    Devuelve (caballo_ganador | None, nota explicativa).
    """
    pos_a = positions.get(horse_a)
    pos_b = positions.get(horse_b)

    if pos_a is not None and pos_b is not None:
        if pos_a == pos_b:
            return None, (
                f"Ambos empataron en la posición {pos_a}° del marcador oficial: "
                "reembolso total sin comisión."
            )
        if pos_a < pos_b:
            return horse_a, (
                f"Marcador oficial: N.º {horse_a} llegó {pos_a}° y el N.º {horse_b} "
                f"{pos_b}° — gana el N.º {horse_a}."
            )
        return horse_b, (
            f"Marcador oficial: N.º {horse_b} llegó {pos_b}° y el N.º {horse_a} "
            f"{pos_a}° — gana el N.º {horse_b}."
        )

    if pos_a is not None:
        return horse_a, (
            f"Marcador oficial: N.º {horse_a} llegó {pos_a}°; el N.º {horse_b} quedó "
            f"fuera del top 5 (no clasificado) — gana el N.º {horse_a}."
        )
    if pos_b is not None:
        return horse_b, (
            f"Marcador oficial: N.º {horse_b} llegó {pos_b}°; el N.º {horse_a} quedó "
            f"fuera del top 5 (no clasificado) — gana el N.º {horse_b}."
        )
    return None, (
        f"Ninguno clasificó en el top 5 (N.º {horse_a} y N.º {horse_b} fuera del "
        "marcador): reembolso total sin comisión."
    )


# ─────────────────────────────── Seed inicial ───────────────────────────────
def seed_initial_data() -> None:
    """Crea las tablas y siembra: administrador, los 19 tipos de duelo y fila bancaria."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from security import hash_password

        if db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first() is None:
            db.add(
                User(
                    username=DEFAULT_ADMIN_USERNAME,
                    password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                    balance=0.0,
                    role=ROLE_ADMIN,
                )
            )

        # Carga/Refresco de los 19 tipos de duelo predefinidos
        db.query(DuelType).delete()
        initial_types = [
            DuelType(name="PELO a PELO", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro."),
            DuelType(name="1y2N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, con el 2do Pierdes la Mitad."),
            DuelType(name="2N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, con el 2do Empatas."),
            DuelType(name="2y2N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, con el 2do Ganas la Mitad."),
            DuelType(name="2 PUESTOS", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro y con el 2do."),
            DuelType(name="2y3N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro y el 2do, con el 3ro Pierdes la Mitad."),
            DuelType(name="3N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro y el 2do, con el 3ro Empatas."),
            DuelType(name="3y3N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro y el 2do, con el 3ro Ganas la Mitad."),
            DuelType(name="3 PUESTOS", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do y el 3ro."),
            DuelType(name="3y4N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do y 3ro, con el 4to Pierdes la Mitad."),
            DuelType(name="4N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do y 3ro, con el 4to Empatas."),
            DuelType(name="4y4N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do y el 3ro, con el 4to Ganas la Mitad."),
            DuelType(name="4 PUESTOS", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do, 3ro y el 4to."),
            DuelType(name="4y5N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do, 3ro y 4to, con el 5to Pierdes la Mitad."),
            DuelType(name="5N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do, 3ro y 4to, con el 5to Empatas."),
            DuelType(name="5y5N", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do, 3ro y el 4to, con el 5to Ganas la Mitad."),
            DuelType(name="5 PUESTOS", logic_rule=RULE_OFFICIAL, description="Ganas con el 1ro, 2do, 3ro, 4to y el 5to."),
            DuelType(name="MARCAS", logic_rule=RULE_OFFICIAL, description="Caballo vs Caballo.", is_matchup=True),
            DuelType(name="MOROCHA", logic_rule=RULE_OFFICIAL, description="2 Caballos vs 2 Caballos.", is_morocha=True),
        ]
        db.add_all(initial_types)

        if db.query(BankInfo).count() == 0:
            db.add(BankInfo())

        db.commit()
    finally:
        db.close()