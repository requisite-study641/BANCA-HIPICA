"""
Banca Hípica P2P — Comprobaciones integrales de integración (E2E).

Ejecuta de forma **secuencial y automatizada** todos los flujos críticos de la
aplicación con ``fastapi.testclient.TestClient`` sobre una base de datos
TEMPORAL y aislada (variable de entorno ``BANCA_DB_PATH`` = ``tests/.tmp_checks.db``),
por lo que **nunca** toca la base de datos de producción (``backend/banca_hipica.db``).

Uso (desde la raíz del proyecto):
    python tests/run_checks.py

Termina con código 0 si todo pasa (``EXITO``) o 1 si algo falla (``FALLO``).
Las pruebas son secuenciales: al fallar una, se omiten las siguientes porque
dependen del estado construido anteriormente.

**Cómo ampliarlo:** añade una función decorada con ``@check("Nombre")`` en el
orden deseado; el runner la ejecutará automáticamente con el contexto compartido
``ctx`` (diccionario con ``client``, tokens, ids, …).
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
TEST_DB = TESTS_DIR / ".tmp_checks.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ─────────────────────────── Registro de comprobaciones ───────────────────────────
CHECKS: List[Tuple[str, Callable[[dict], None]]] = []


def check(name: str) -> Callable:
    """Decorador que registra una comprobación secuencial."""

    def decorator(fn: Callable[[dict], None]) -> Callable[[dict], None]:
        CHECKS.append((name, fn))
        return fn

    return decorator


# ─────────────────────────────── Utilidades ───────────────────────────────
def must(condition: bool, message: str) -> None:
    """Asertiva con mensaje claro (equivale a un assert personalizado)."""
    if not condition:
        raise AssertionError(message)


def approx(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(float(a) - float(b)) <= tol


def auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client, username: str, password: str) -> dict:
    response = client.post("/auth/login", json={"username": username, "password": password})
    must(
        response.status_code == 200,
        f"login de '{username}' devolvió {response.status_code}: {response.text}",
    )
    return response.json()


def balance_of(client, token: str) -> float:
    response = client.get("/auth/me", headers=auth(token))
    must(response.status_code == 200, f"/auth/me devolvió {response.status_code}")
    return float(response.json()["balance"])


def type_id_by_rule(client, rule: str) -> int:
    """Localiza un tipo de duelo sembrado por su regla lógica."""
    response = client.get("/duel-types")
    must(response.status_code == 200, "no se pudo leer GET /duel-types")
    for item in response.json():
        if item["logic_rule"] == rule:
            return int(item["id"])
    raise AssertionError(f"no existe un tipo de duelo con regla '{rule}'")


def upload_file(client, token: str, filename: str, payload: bytes):
    """POST /admin/races/upload con archivo multipart."""
    return client.post(
        "/admin/races/upload",
        files={"file": (filename, payload, "text/csv")},
        headers=auth(token),
    )


# ───────────────────────── Entorno de prueba (BD aislada) ─────────────────────────
def prepare():
    """
    Limpia la BD temporal, fija ``BANCA_DB_PATH`` e importa la aplicación.

    El orden importa: la variable de entorno DEBE fijarse ANTES de importar
    ``backend.main`` (que crea el motor de SQLite al importar ``backend.database``).
    """
    for suffix in ("", "-journal", "-wal", "-shm"):
        stale = Path(str(TEST_DB) + suffix)
        if stale.exists():
            stale.unlink()

    os.environ["BANCA_DB_PATH"] = str(TEST_DB)

    from fastapi.testclient import TestClient  # import diferido a propósito
    from backend.main import app

    return TestClient, app


# ─────────────────────── Datos de prueba (cartelera) ───────────────────────
# Reporte INH codificado en latin-1 (con tildes) — valida la cadena de decodificación.
INH_PAYLOAD = (
    "EJEMPLARES INSCRITOS - REUNIÓN 39\r\n"
    "\r\n"
    "Carrera Nro: 1\r\n"
    "Fecha: 06/10/2026\r\n"
    "Hora: 14:30\r\n"
    "Distancia: 1.200 m\r\n"
    "\r\n"
    "N°;Ejemplar;Edad;Sexo\r\n"
    "1;Torpedo Relámpago;4;M\r\n"
    "2;Caribe Dorado;5;H\r\n"
    "3;Rey del Polvo;4;M\r\n"
    "4;Medianoche Azul;6;H\r\n"
).encode("latin-1")

# CSV plano en UTF-8: carrera 7 con 7 ejemplares (5 en el top 5 y 2 fuera).
FLAT_PAYLOAD = (
    "numero_caballo,nombre_caballo,numero_carrera,fecha,hora\n"
    + "\n".join(f"{n},Ejemplar Test {n},7,2026-10-06,16:00" for n in range(1, 8))
).encode("utf-8")

# Reporte INH incompleto (falta la hora) → debe rechazarse atómicamente.
BROKEN_INH = (
    "Carrera Nro: 9\r\n"
    "Fecha: 06/10/2026\r\n"
    "\r\n"
    "N°;Ejemplar\r\n"
    "1;Caballo Sin Hora\r\n"
).encode("latin-1")

# CSV sin las columnas requeridas.
BAD_CSV = "columna_a,columna_b\n1,2\n".encode("utf-8")

# Marcador oficial de la carrera 7 (5 posiciones con caballos distintos).
OFFICIAL_R7 = [
    {"position": 1, "horse_number": 3},
    {"position": 2, "horse_number": 1},
    {"position": 3, "horse_number": 5},
    {"position": 4, "horse_number": 2},
    {"position": 5, "horse_number": 4},
]


# ───────────────────────── 1. Autenticación y roles ─────────────────────────
@check("1. Salud, registro, login y roles (admin por defecto)")
def check_auth(ctx):
    client = ctx["client"]

    health = client.get("/health")
    must(health.status_code == 200, "GET /health debe responder 200")
    must(health.json().get("status") == "ok", "GET /health debe devolver status=ok")

    # Sin token → 401
    must(
        client.get("/duels/available").status_code == 401,
        "GET /duels/available sin token debe devolver 401",
    )

    # Administrador sembrado por la aplicación
    admin = login(client, "admin", "admin123")
    must(admin["user"]["role"] == "admin", "la cuenta inicial debe tener rol 'admin'")
    me = client.get("/auth/me", headers=auth(admin["token"]))
    must(me.status_code == 200 and me.json()["username"] == "admin", "/auth/me del admin falló")

    # Credenciales inválidas
    bad = client.post("/auth/login", json={"username": "admin", "password": "incorrecta"})
    must(bad.status_code == 401, "login con contraseña incorrecta debe devolver 401")

    # Registro de usuario normal (rol user y balance 0)
    registered = client.post(
        "/auth/register", json={"username": "jugador_e2e", "password": "jugador123"}
    )
    must(registered.status_code == 201, f"registro devolvió {registered.status_code}: {registered.text}")
    body = registered.json()
    must(body["user"]["role"] == "user", "el registro público siempre crea rol 'user'")
    must(approx(body["user"]["balance"], 0.0), "un usuario nuevo debe nacer con balance 0")

    ctx["admin_token"] = admin["token"]
    ctx["user_token"] = body["token"]
    ctx["username"] = body["user"]["username"]


@check("2. Roles: usuario normal bloqueado en rutas de administración")
def check_roles(ctx):
    client, user = ctx["client"], ctx["user_token"]

    must(
        client.get("/admin/audit", headers=auth(user)).status_code == 403,
        "un usuario normal en GET /admin/audit debe recibir 403",
    )
    must(
        client.post(
            "/admin/duel-types",
            headers=auth(user),
            json={"name": "Intento", "logic_rule": "MANUAL"},
        ).status_code
        == 403,
        "un usuario normal no puede crear tipos de duelo (403)",
    )
    must(
        client.get("/admin/duels", headers=auth(user)).status_code == 403,
        "un usuario normal no puede ver /admin/duels (403)",
    )


# ────────────────── 3. CRUD de tipos de duelo (reglas) ──────────────────
@check("3. CRUD de tipos de duelo (reglas lógicas y OFFICIAL_FINISH)")
def check_duel_types(ctx):
    client, admin = ctx["client"], ctx["admin_token"]

    rules = {item["logic_rule"] for item in client.get("/duel-types").json()}
    required = {"LOWEST_HORSE_NUMBER", "HIGHEST_HORSE_NUMBER", "MANUAL", "TIE_REFUND", "OFFICIAL_FINISH"}
    must(required <= rules, f"el seed debe incluir {required}; se obtuvo {rules}")

    # Crear
    created = client.post(
        "/admin/duel-types",
        headers=auth(admin),
        json={"name": "Tipo E2E temporal", "logic_rule": "MANUAL", "description": "creado por run_checks"},
    )
    must(created.status_code == 201, f"POST /admin/duel-types → {created.status_code}: {created.text}")
    type_id = created.json()["id"]

    # Regla inválida → 400
    invalid = client.post(
        "/admin/duel-types",
        headers=auth(admin),
        json={"name": "Regla mala", "logic_rule": "NO_EXISTE"},
    )
    must(invalid.status_code == 400, "una regla lógica inválida debe devolver 400")

    # Modificar (cambia a OFFICIAL_FINISH)
    updated = client.put(
        f"/admin/duel-types/{type_id}",
        headers=auth(admin),
        json={"name": "Tipo E2E oficial", "logic_rule": "OFFICIAL_FINISH", "description": "actualizado"},
    )
    must(updated.status_code == 200, f"PUT /admin/duel-types/{{id}} → {updated.status_code}")
    must(updated.json()["logic_rule"] == "OFFICIAL_FINISH", "la modificación debe conservar OFFICIAL_FINISH")

    # Eliminar (sin duelos asociados) y comprobar 404 posterior
    deleted = client.delete(f"/admin/duel-types/{type_id}", headers=auth(admin))
    must(deleted.status_code == 200, f"DELETE /admin/duel-types/{{id}} → {deleted.status_code}")
    must(
        client.delete(f"/admin/duel-types/{type_id}", headers=auth(admin)).status_code == 404,
        "eliminar dos veces debe devolver 404",
    )


# __CHECKS_PART3__



# ───────────────────────── 4. Cartelera (INH + CSV plano) ─────────────────────────
@check("4. Carga de cartelera (formato INH latin-1 y CSV plano)")
def check_races(ctx):
    client, admin = ctx["client"], ctx["admin_token"]

    resp = upload_file(client, admin, "reunion39.csv", INH_PAYLOAD)
    must(resp.status_code == 200, f"upload INH -> {resp.status_code}: {resp.text}")
    body = resp.json()
    must(body["imported"] >= 4, f"INH: debe importar >=4 ejemplares, se importaron {body['imported']}")
    must(body["total_rows"] == 4, f"INH: total_rows debe ser 4, se obtuvo {body['total_rows']}")
    must(body["race_numbers"] == [1], f"INH: debe cargar carrera 1, se obtuvo {body['race_numbers']}")

    entries = client.get("/races").json()
    race1 = [r for r in entries if r["race_number"] == 1]
    must(len(race1) == 4, "la carrera 1 debe tener 4 ejemplares")
    must({r["horse_number"] for r in race1} == {1, 2, 3, 4}, "la carrera 1 debe tener caballos 1-4")

    resp2 = upload_file(client, admin, "cartelera_flat.csv", FLAT_PAYLOAD)
    must(resp2.status_code == 200, f"upload CSV -> {resp2.status_code}: {resp2.text}")
    body2 = resp2.json()
    must(body2["imported"] >= 7, f"CSV: debe importar >=7 ejemplares, se importaron {body2['imported']}")

    race7 = [r for r in entries if r["race_number"] == 7]
    must(len(race7) == 7, "la carrera 7 debe tener 7 ejemplares")
    numbers = sorted(r["horse_number"] for r in race7)
    must(numbers == [1, 2, 3, 4, 5, 6, 7], f"carrera 7 debe tener caballos 1-7, se obtuvo {numbers}")

    resp3 = upload_file(client, admin, "reunion39_roto.csv", BROKEN_INH)
    must(resp3.status_code == 400, f"INH rotos debe dar 400: {resp3.text}")
    must("errors" in resp3.json(), "INH rotos debe incluir 'errors' en la respuesta")

    resp4 = upload_file(client, admin, "mal.csv", BAD_CSV)
    must(resp4.status_code == 400, f"CSV malo debe dar 400: {resp4.text}")


# ───────────────────────── 5. Creacion de duelo con escrow (5% casa) ─────────────────────────
@check("5. Creacion de duelo con escrow y retencion del 5%")
def check_duel_create(ctx):
    client, admin, user = ctx["client"], ctx["admin_token"], ctx["user_token"]

    topup = client.post(
        "/payments/topup",
        headers=auth(user),
        json={"amount": 1000, "reference": "E2E-001", "wallet_phone": "+34 600 000 001"},
    )
    must(topup.status_code == 201, f"topup -> {topup.status_code}: {topup.text}")
    topup_id = topup.json()["id"]
    approved = client.post(f"/admin/topups/{topup_id}/approve", headers=auth(admin))
    must(approved.status_code == 200, f"approve topup -> {approved.status_code}: {approved.text}")
    must(approx(approved.json()["new_balance"], 1000.0), "el saldo del usuario debe ser 1000")

    type_off = type_id_by_rule(client, "OFFICIAL_FINISH")
    race_number = 7

    stake = 100.0
    duel = client.post(
        "/duels/create",
        headers=auth(user),
        json={"duel_type_id": type_off, "race_number": race_number,
              "horse_creator": 1, "horse_opponent": 2, "stake": stake},
    )
    must(duel.status_code == 201, f"create duel -> {duel.status_code}: {duel.text}")
    dup = duel.json()
    must(dup["status"] == "OPEN", "el duelo debe quedar en OPEN")
    must(dup["duel_type_name"] == "Posiciones oficiales (top 5)", "tipo de duelo aplicado")
    must(dup["horse_creator"] == 1 and dup["horse_opponent"] == 2, "caballos en pugna")
    must(dup["stake"] == stake, f"stake guardado = {dup['stake']}")

    balance = balance_of(client, user)
    must(approx(balance, 900.0, tol=0.05), f"escrow: balance = {balance}, se esperaba 900")

    available = client.get("/duels/available", headers=auth(user)).json()
    must(any(d["id"] == dup["id"] for d in available), "el duelo debe estar disponible")
    ctx["duel_id"] = dup["id"]
    ctx["duel_stake"] = stake
    ctx["duel_creator_id"] = dup["creator_id"]


# ───────────────────────── 6. Registro de posiciones oficiales (1° al 5°) ─────────────────────────
@check("6. Marcador oficial guardado (1° al 5°) + previsualizacion de duelos activos")
def check_official_results(ctx):
    client, admin = ctx["client"], ctx["admin_token"]

    positions = [
        {"position": 1, "horse_number": 3},
        {"position": 2, "horse_number": 1},
        {"position": 3, "horse_number": 5},
        {"position": 4, "horse_number": 2},
        {"position": 5, "horse_number": 4},
    ]
    res = client.post(
        f"/admin/races/7/official-results",
        headers=auth(admin),
        json={"positions": positions},
    )
    must(res.status_code == 200, f"official-results -> {res.status_code}: {res.text}")
    body = res.json()
    must(body["has_results"] is True, "debe marcar has_results=True")
    must(body["top_n"] == 5, "top_n debe ser 5")
    must(len(body["results"]) == 5, "deben guardarse exactamente 5 posiciones")

    must(len(body["active_duels"]) >= 1, "debe haber duelos activos para mostrar previsualizacion")
    duel = next((d for d in body["active_duels"] if d["duel_id"] == ctx["duel_id"]), None)
    must(duel is not None, "debe aparecer la previsualizacion del duelo E2E")
    must(duel["suggested_winner_horse"] == 1, f"ganador sugerido = caballo 1 (creador), se obtuvo {duel['suggested_winner_horse']}")


# ───────────────────────── 7. Resolucion de duelo activo (payout + comision 5%) ─────────────────────────
@check("7. Resolucion de duelo activo (payout 95% / comision 5%) y reembolso si ambos fuera del top 5")
def check_duel_resolution(ctx):
    client, admin, user = ctx["client"], ctx["admin_token"], ctx["user_token"]
    duel_id = ctx["duel_id"]
    stake = ctx["duel_stake"]

    accept = client.post(f"/duels/{duel_id}/accept", headers=auth(admin))
    must(accept.status_code == 200, f"accept duel -> {accept.status_code}: {accept.text}")
    must(accept.json()["status"] == "ACTIVE", "el duelo debe ser ACTIVE tras aceptar")
    must(approx(balance_of(client, user), 800.0, tol=0.05), "balance tras aceptar = 900 - 100 = 800")

    resolve = client.post(
        f"/admin/duels/{duel_id}/resolve",
        headers=auth(admin),
        json={"winner_horse_number": 1, "note": "Aplique el marcador oficial"},
    )
    must(resolve.status_code == 200, f"resolve duel -> {resolve.status_code}: {resolve.text}")
    body = resolve.json()
    must(body["status"] == "RESOLVED", "el duelo debe ser RESOLVED")
    must(body["winner_horse_number"] == 1, "el ganador debe ser el caballo 1 (creador)")
    expected_comm = round(stake * 2 * 0.05, 2)
    expected_payout = round(stake * 2 * 0.95, 2)
    must(approx(body.get("commission", 0.0), expected_comm, tol=0.01),
         f"comision = 5% del pozo = {expected_comm}, se obtuvo {body.get('commission')}")
    must(approx(body.get("payout", 0.0), expected_payout, tol=0.01),
         f"payout = 95% del pozo = {expected_payout}, se obtuvo {body.get('payout')}")

    final_balance = balance_of(client, user)
    must(approx(final_balance, 990.0, tol=0.05), f"balance final = {final_balance}, se esperaba 990")


# ───────────────────────── 7b. Reembolso cuando ambos fuera del top 5 ─────────────────────────
@check("7b. Reembolso total sin comision cuando ambos caballos quedan fuera del top 5")
def check_duel_refund(ctx):
    client, admin, user = ctx["client"], ctx["admin_token"], ctx["user_token"]
    race_number = 7
    stake = 100.0

    type_off = type_id_by_rule(client, "OFFICIAL_FINISH")

    duel = client.post(
        "/duels/create",
        headers=auth(user),
        json={"duel_type_id": type_off, "race_number": race_number,
              "horse_creator": 6, "horse_opponent": 7, "stake": stake},
    )
    must(duel.status_code == 201, f"create duel (fuera del top 5) -> {duel.status_code}: {duel.text}")
    dup = duel.json()
    must(dup["status"] == "OPEN", "el duelo debe quedar en OPEN")
    duel_id = dup["id"]
    ctx["duel_refund_id"] = duel_id

    accept = client.post(f"/duels/{duel_id}/accept", headers=auth(admin))
    must(accept.status_code == 200, f"accept duel (fuera del top 5) -> {accept.status_code}")
    must(accept.json()["status"] == "ACTIVE", "el duelo debe ser ACTIVE tras aceptar")

    resolve = client.post(
        f"/admin/duels/{duel_id}/resolve",
        headers=auth(admin),
        json={"winner_horse_number": 6, "note": "Ambos fuera del top 5 -> reembolso"},
    )
    must(resolve.status_code == 200, f"resolve duel (both outside) -> {resolve.status_code}: {resolve.text}")
    body = resolve.json()
    must(body["status"] == "RESOLVED", "el duelo debe ser RESOLVED")
    must(body.get("refund") is True, "debe indicar refund=True")
    must(approx(body.get("commission", 0.0), 0.0, tol=0.01), "la comision debe ser 0 en reembolso")
    must(approx(body.get("payout", 0.0), 0.0, tol=0.01), "el payout debe ser 0 en reembolso")

    final_balance = balance_of(client, user)
    must(approx(final_balance, 890.0, tol=0.05),
         f"balance tras reembolso = {final_balance}, se esperaba 890")


# ───────────────────────── 8. Recargas, retiros y auditoria ─────────────────────────
@check("8. Recargas, retiros y auditoria de balances/comisiones")
def check_payments(ctx):
    client, admin, user = ctx["client"], ctx["admin_token"], ctx["user_token"]

    topup = client.post(
        "/payments/topup", headers=auth(user),
        json={"amount": 250, "reference": "E2E-TOP", "wallet_phone": "+34 600 000 002"},
    )
    must(topup.status_code == 201, f"topup -> {topup.status_code}: {topup.text}")
    topup_id = topup.json()["id"]
    must(client.post(f"/admin/topups/{topup_id}/approve", headers=auth(admin)).status_code == 200,
         "approve topup")
    must(approx(balance_of(client, user), 1140.0, tol=0.05), "balance tras recarga = 890 + 250")

    pending = client.get("/admin/topups", headers=auth(admin)).json()
    must(any(t["id"] == topup_id and t["status"] == "APPROVED" for t in pending),
         "la recarga debe estar APPROVED en la cola admin")

    audit = client.get("/admin/audit", headers=auth(admin)).json()
    must(audit["duels"]["resolved"] >= 2, "deben existir >=2 duelos resueltos")
    must(approx(audit["duels"]["commissions"], 20.0, tol=0.05),
         f"comisiones totales = {audit['duels']['commissions']}")


# ───────────────────────── 9. Resumen de arquitectura E2E ─────────────────────────
@check("9. Arquitectura E2E: estado final de la aplicacion")
def check_integration(ctx):
    client, admin = ctx["client"], ctx["admin_token"]

    me = client.get("/auth/me", headers=auth(ctx["user_token"])).json()
    user = me["user"]
    must(user["role"] == "user", "el usuario de prueba conserva rol 'user'")
    must(approx(user["balance"], 1140.0, tol=0.05), f"balance final = {user['balance']}, se esperaba 1140")

    duel_id = ctx["duel_id"]
    duel = client.get(f"/duels/{duel_id}", headers=auth(ctx["user_token"])).json()
    must(duel["status"] == "RESOLVED", "el duelo principal debe estar RESOLVED")

    duel_refund_id = ctx.get("duel_refund_id")
    if duel_refund_id:
        duel_ref = client.get(f"/duels/{duel_refund_id}", headers=auth(ctx["user_token"])).json()
        must(duel_ref["status"] == "RESOLVED", "el duelo de reembolso debe estar RESOLVED")

    admin_balance = balance_of(client, admin)
    must(admin_balance >= 0.0, f"el balance del admin no puede ser negativo: {admin_balance}")

    print("\n" + "=" * 60)
    print("  E2E INTEGRATION SUMMARY")
    print("=" * 60)
    print(f"  - Duelo principal: RESOLVED (payout {round(ctx['duel_stake']*2*0.95,2)} / comision 5%)")
    if duel_refund_id:
        print(f"  - Duelo de reembolso: RESOLVED (ambos fuera del top 5)")
    print(f"  - Balance del usuario de prueba: {round(user['balance'], 2)}")
    print(f"  - Marcador oficial: 1°: caballo 3, 2°: caballo 1, 3°: caballo 5, 4°: caballo 2, 5°: caballo 4")
    print("=" * 60)



