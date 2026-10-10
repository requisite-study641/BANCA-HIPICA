"""Gestor de respaldos automaticos para la aplicacion Banca Hípica P2P.

Este script:
    1. Verifica que el test suite de integracion (tests/run_e2e.py) se haya
       ejecutado exitosamente y valide todas las comprobaciones E2E.
    2. Si todas las comprobaciones finalizaron con EXITO, genera un archivo
       comprimido de respaldo con cabecera en backups/backup_YYYYMMDD_HHMMSS.zip
       que contiene:
          - La base de datos SQLite activa (backend/banca_hipica.db).
          - El codigo fuente completo (backend/ y frontend/).
          - El archivo de bitacora tecnica (CONTEXT.md).
          - Los scripts de pruebas y comprobacion (tests/).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
BACKUPS_DIR = ROOT / "backups"
MANIFEST_PATH = BACKUPS_DIR / "manifest.json"


def ensure_started() -> None:
    """Crea los directorios necesarios si no existen."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def run_tests() -> bool:
    """Ejecuta el test suite y devuelve True si finaliza con EXITO."""
    print(">>> Ejecutando test suite de integracion (tests/run_e2e.py)...")
    try:
        result = subprocess.run(
            [sys.executable, "tests/run_e2e.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:
        print(f"  [ERROR] no se pudo ejecutar el test suite: {exc}")
        return False

    print(result.stdout)
    if result.stderr:
        print("--- salida estandar de error ---")
        print(result.stderr)

    if result.returncode != 0:
        print(f"  [ERROR] test suite finalizó con codigo {result.returncode}")
        return False

    # Validacion critica: busqueda de un marcador vislumbrado de EXITO.
    if "EXITO" not in result.stdout and "paso" not in result.stdout.lower():
        print("  [ERROR] no se detecto un resultado de EXITO en la ejecucion.")
        return False

    print("  [OK] test suite finalizó con EXITO.")
    return True


def create_backup() -> Path:
    """Crea un respaldo comprimido con cabecera y devuelve la ruta del archivo."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUPS_DIR / f"backup_{timestamp}"
    zip_path = BACKUPS_DIR / f"backup_{timestamp}.zip"

    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. Base de datos SQLite activa.
    db_src = ROOT / "backend" / "banca_hipica.db"
    if db_src.exists():
        shutil.copy2(db_src, backup_dir / "banca_hipica.db")

    # 2. Codigo fuente: backend/ y frontend/.
    for folder in ("backend", "frontend"):
        source = ROOT / folder
        if source.exists():
            shutil.copytree(source, backup_dir / folder, dirs_exist_ok=True)

    # 3. Bitacora tecnica.
    if (ROOT / "CONTEXT.md").exists():
        shutil.copy2(ROOT / "CONTEXT.md", backup_dir / "CONTEXT.md")

    # 4. Scripts de pruebas y comprobacion.
    if TESTS_DIR.exists():
        shutil.copytree(
            TESTS_DIR, backup_dir / "tests", dirs_exist_ok=True
        )

    # Generar un archivo de texto con la lista de archivos incluidos.
    manifest = {
        "timestamp": timestamp,
        "backup_directory": str(backup_dir),
        "zip_path": str(zip_path),
        "included_items": [
            "banca_hipica.db",
            "backend/",
            "frontend/",
            "CONTEXT.md",
            "tests/",
        ],
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(backup_dir.rglob("*")):
            if item.is_file():
                arcname = item.relative_to(backup_dir)
                zf.write(item, arcname)

    # Sobrescribir el manifest persistido con la ultima operacion.
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"  [OK] Respaldo creado: {zip_path}")
    return zip_path


def main() -> int:
    ensure_started()
    tests_ok = run_tests()

    if not tests_ok:
        print("  [ERROR] Las pruebas no pasaron; no se crea respaldo.")
        return 1

    create_backup()
    print("  [OK] Respaldo generado correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
