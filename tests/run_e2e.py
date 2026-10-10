"""Ejecucion completa de las comprobaciones E2E.

Esta es la entrada principal para ejecutar el test suite de integracion.
Usar desde la raiz del proyecto:

    python tests/run_e2e.py

Comportamiento:
    - Abre una base de datos SQLite TEMPORAL y aislada (tests/.tmp_checks.db),
      por lo que nunca toca la base de datos de produccion (backend/banca_hipica.db).
    - Instancia la aplicacion FastAPI con TestClient y ejecuta las comprobaciones
      registradas en tests/run_checks.py en orden.
    - Imprime un resumen de cada comprobacion y termina con exit code 0 si
      todas pasan o 1 si falla alguna.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
TEST_DB = TESTS_DIR / ".tmp_checks.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Columna de la base de datos temporal que no se toca nunca en produccion.
os.environ["BANCA_DB_PATH"] = str(TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from backend import database, main as app  # noqa: E402
from tests.run_checks import run_all  # noqa: E402


def main() -> int:
    ctx = {
        "client": TestClient(main.app),
        "admin_token": None,
        "user_token": None,
    }

    # ---- 1. Registrar y loguear administrador ----
    reg = ctx["client"].post(
        "/auth/register",
        json={"username": "e2e_admin", "password": "admin123"},
    )
    if reg.status_code != 201:
        print(f"[FALLO] register admin -> {reg.status_code}: {reg.text}")
        return 1
    login = ctx["client"].post(
        "/auth/login",
        json={"username": "e2e_admin", "password": "admin123"},
    )
    if login.status_code != 200:
        print(f"[FALLO] login admin -> {login.status_code}: {login.text}")
        return 1
    ctx["admin_token"] = login.json()["token"]

    # ---- 2. Registrar y loguear usuario de prueba ----
    reg2 = ctx["client"].post(
        "/auth/register",
        json={"username": "e2e_user", "password": "user123"},
    )
    if reg2.status_code != 201:
        print(f"[FALLO] register user -> {reg2.status_code}: {reg2.text}")
        return 1
    login2 = ctx["client"].post(
        "/auth/login",
        json={"username": "e2e_user", "password": "user123"},
    )
    if login2.status_code != 200:
        print(f"[FALLO] login user -> {login2.status_code}: {login2.text}")
        return 1
    ctx["user_token"] = login2.json()["token"]

    # ---- 3. Ejecutar todas las comprobaciones en orden ----
    ok, last_error = run_all(ctx)

    if not ok:
        print(f"\n[ERROR] ultima comprobacion fallida: {last_error}")
        traceback.print_exc()
        return 1

    print("\n  [OK] Todas las comprobaciones E2E pasaron con EXITO.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("\n[ERROR] error inesperado durante la ejecucion del test suite.")
        traceback.print_exc()
        sys.exit(1)
