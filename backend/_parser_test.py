"""Prueba integrativa del parser de cartelera (edición)."""
import os
import sys

ROOT = "c:/BANCA HIPICA"
sys.path.insert(0, ROOT)

TEST_DB = os.path.join(ROOT, "tests", ".tmp_checks.db")
os.environ["BANCA_DB_PATH"] = TEST_DB

from fastapi.testclient import TestClient  # noqa: E402

from backend import database, main as app  # noqa: E402

# Limpiar BD temporal
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

database.seed_initial_data()
client = TestClient(app.app)

# 1. Login admin
r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, r.text
token = r.json()["token"]
print("[OK] Login admin")

# 2. Cargar cartelera INH (latin-1)
with open(os.path.join(ROOT, "frontend", "ejemplares_inh_ejemplo.csv"), "rb") as f:
    raw = f.read()

r = client.post(
    "/admin/races/upload",
    files={"file": ("reporte_inh.csv", raw, "latin-1")},
    headers={"Authorization": f"Bearer {token}"},
)
print(f"Upload INH: {r.status_code} {r.text[:300]}")
assert r.status_code == 200, r.text
data = r.json()
print(f"  formato={data['format']} cod={data['encoding']} nuevos={data['imported']} total={data['total_rows']}")
assert data["imported"] == 4, f"Se importaron {data['imported']} ejemplares, se esperaban 4"
print("[OK] Carga INH cartelera (4 ejemplares)")

# 3. Verificar datos en BD
from backend import database
db = database.SessionLocal()
count = db.query(database.RaceEntry).count()
print(f"  RaceEntries en BD: {count}")
assert count == 4, f"Se esperaban 4 RaceEntries, se tienen {count}"
db.close()
print("[OK] Datos en SQLite")

# Cleanup
db = database.SessionLocal()
db.close()
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

# 4. Limpiar y repetir con CSV plano
database.seed_initial_data()
client2 = TestClient(app.app)
r = client2.post("/auth/login", json={"username": "admin", "password": "admin123"})
token2 = r.json()["token"]

csv_text = "numero_caballo,nombre_caballo,numero_carrera,fecha,hora\n1,Run Man Run,3,06/10/2026,16:00\n2,Super Chic,3,06/10/2026,16:00\n"
r = client2.post(
    "/admin/races/upload",
    content=csv_text.encode("utf-8"),
    headers={"Authorization": f"Bearer {token2}"},
)
print(f"Upload CSV: {r.status_code} {r.text[:300]}")
assert r.status_code == 200, r.text
data = r.json()
print(f"  formato={data['format']} nuevos={data['imported']} total={data['total_rows']}")
assert data["imported"] == 2, f"Se importaron {data['imported']} ejemplares, se esperaban 2"
db = database.SessionLocal()
count = db.query(database.RaceEntry).count()
print(f"  RaceEntries en BD: {count}")
assert count == 2, f"Se esperaban 2 RaceEntries, se tienen {count}"
db.close()

# 5. Verificar que el parser detecta formatos
from backend.parsers import detect_format, parse_cartelera

with open(os.path.join(ROOT, "frontend", "ejemplares_inh_ejemplo.csv"), "rb") as f:
    inh = f.read()
with open(os.path.join(ROOT, "frontend", "cartelera_ejemplo.csv"), "rb") as f:
    csv_flat = f.read()

assert detect_format(inh.decode("latin-1")) == "INH"
assert detect_format(csv_flat.decode("utf-8")) == "CSV"
print("[OK] Detección de formato automática")

print("\n✅ Todas las pruebas pasaron con EXITO.")
