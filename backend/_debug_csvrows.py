import sys, csv, io
sys.path.insert(0, ".")
from backend.parsers import _read_xlsx

raw = open("Ejemplares inscritos reunión 39.xlsx", "rb").read()
text = _read_xlsx(raw)
r = csv.reader(io.StringIO(text), delimiter=";", quotechar='"')
for i, row in enumerate(r):
    print(i, row)
