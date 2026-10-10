"""Esquemas Pydantic para las peticiones y respuestas de la API."""

from typing import List, Optional

from pydantic import BaseModel, Field


# ───────────────────────────── Auth / usuarios ─────────────────────────────
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=4, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    balance: float
    role: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ────────────────────────── Tipos de duelo (Admin) ──────────────────────────
class DuelTypeCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    logic_rule: str = Field(min_length=3, max_length=60)
    description: str = ""
    is_matchup: bool = False
    is_morocha: bool = False


class DuelTypeUpdate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    logic_rule: str = Field(min_length=3, max_length=60)
    description: str = ""
    is_matchup: bool = False
    is_morocha: bool = False


class DuelTypeOut(BaseModel):
    id: int
    name: str
    logic_rule: str
    description: str = ""
    is_matchup: bool = False
    is_morocha: bool = False

    class Config:
        from_attributes = True


# ────────────────────────────────── Duelos ──────────────────────────────────
class DuelCreate(BaseModel):
    """El creador elige: tipo de duelo, carrera, su caballo, el caballo rival y el stake."""

    duel_type_id: int
    race_number: int
    horse_creator: int
    horse_opponent: int
    horse_creator_2: Optional[int] = None
    horse_opponent_2: Optional[int] = None
    stake: float = Field(gt=0, description="Monto de apuesta retenido en escrow")


class DuelOut(BaseModel):
    id: int
    duel_type_id: int
    race_number: int
    race_datetime: Optional[str] = None
    horse_creator: int
    horse_creator_name: Optional[str] = ""
    horse_opponent: int
    horse_opponent_name: Optional[str] = ""
    horse_creator_2: Optional[int] = None
    horse_creator_2_name: Optional[str] = ""
    horse_opponent_2: Optional[int] = None
    horse_opponent_2_name: Optional[str] = ""
    horse_acceptor: Optional[int] = None
    stake: float
    fee_percentage: float
    status: str
    creator_id: int
    acceptor_id: Optional[int] = None
    winner_id: Optional[int] = None
    winner_horse_number: Optional[int] = None
    commission_amount: Optional[float] = None
    payout_amount: Optional[float] = None
    resolution_note: Optional[str] = None
    created_at: Optional[str] = None
    accepted_at: Optional[str] = None
    resolved_at: Optional[str] = None

    class Config:
        from_attributes = True


class DuelAccept(BaseModel):
    """El oponente acepta igualando el stake."""

    horse_acceptor: Optional[int] = None


class ResolveDuel(BaseModel):
    """Resolución administrativa aplicando la regla lógica del tipo de duelo."""

    winner_horse_number: Optional[int] = None
    note: Optional[str] = None


# ─────────────────────── Pagos móviles / retiros ───────────────────────
class TopUpCreate(BaseModel):
    amount: float = Field(gt=0)
    reference: str = Field(min_length=3, max_length=80)
    wallet_phone: str = Field(min_length=5, max_length=40)


class WithdrawCreate(BaseModel):
    amount: float = Field(gt=0)
    destination_phone: str = Field(min_length=5, max_length=40)
# ───────────────────────────── Gestión bancaria ─────────────────────────────
class BankInfoUpdate(BaseModel):
    bank_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=40)
    id_number: str = Field(min_length=4, max_length=40)
    account_type: str = Field(min_length=2, max_length=40)
    holder_name: str = Field(min_length=3, max_length=120)


# ─────────── Resultados oficiales de carrera (1° al 5° lugar) ───────────
class OfficialResultPosition(BaseModel):
    """Un puesto del marcador oficial (1 = 1er lugar … 5 = 5to lugar)."""

    position: int = Field(ge=1, le=5)
    horse_number: int = Field(ge=1)


class OfficialResultsRequest(BaseModel):
    """Marcador oficial completo de una carrera: exactamente las 5 posiciones."""

    positions: List[OfficialResultPosition]