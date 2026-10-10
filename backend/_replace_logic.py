import sys


def replace_parse_inh_report(filepath):
    with open(filepath, encoding="utf-8") as f:
        lines = f.read().split("\n")

    # Find the parse_inh_report function
    start_line = None
    end_line = None
    for i, line in enumerate(lines):
        if line.startswith("def parse_inh_report"):
            start_line = i + 1  # 1-based
        if start_line is not None and line.strip() == 'return {"format": "INH", "rows": rows, "errors": errors}':
            end_line = i + 1  # 1-based
            break

    if start_line is None or end_line is None:
        print(f"ERROR: Function not found (start={start_line}, end={end_line})")
        sys.exit(1)

    print(f"Replacing lines {start_line} to {end_line}")
    return start_line, end_line


if __name__ == "__main__":
    replace_parse_inh_report("c:/BANCA HIPICA/backend/parsers.py")
