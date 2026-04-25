import json
import re


def generate():
    try:
        with open("coverage.txt", encoding="utf-8") as f:
            t = f.read()
    except UnicodeError:
        with open("coverage.txt", encoding="utf-16") as f:
            t = f.read()

    # Extract percentage from line like: TOTAL ... ... 85%
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", t)
    if not match:
        raise ValueError("Could not find coverage percentage in coverage.txt")

    p = int(match.group(1))

    result = {
        "schemaVersion": 1,
        "label": "coverage",
        "message": f"{p}%",
        "color": ("brightgreen" if p >= 90 else "yellow" if p >= 75 else "red"),
    }

    with open("resources/badges/coverage.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    generate()
