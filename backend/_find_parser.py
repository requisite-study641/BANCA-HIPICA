import sys

p = "c:/BANCA HIPICA/backend/parsers.py"

with open(p, encoding="utf-8") as f:
    lines = f.read().split("\n")

# Find the parse_inh_report function
start_line = None
end_line = None
for i, line in enumerate(lines):
    if line.startswith("def parse_inh_report"):
        start_line = i + 1
    if start_line is not None and line.strip() == 'return {"format": "INH", "rows": rows, "errors": errors}':
        end_line = i + 1
        break

print(f"parse_inh_report: lines {start_line} to {end_line}")
print(f"Total lines in file: {len(lines)}")
