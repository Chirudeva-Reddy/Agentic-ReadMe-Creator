"""csv-dedupe: remove duplicate rows from a CSV file."""
import argparse
import csv
import sys


def dedupe(rows, key=None):
    """Return rows with duplicates removed, keeping the first occurrence."""
    seen, out = set(), []
    for row in rows:
        k = row[key].strip().lower() if key else tuple(v.strip() for v in row.values())
        if k not in seen:
            seen.add(k)
            out.append(row)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Remove duplicate rows from a CSV export.")
    p.add_argument("path", help="CSV file to clean")
    p.add_argument("--key", help="only compare this column (case-insensitive)")
    p.add_argument("-o", "--output", help="write cleaned CSV here (default: stdout)")
    a = p.parse_args()
    with open(a.path, newline="") as f:
        reader = csv.DictReader(f)
        rows, fields = list(reader), reader.fieldnames
    kept = dedupe(rows, a.key)
    out = open(a.output, "w", newline="") if a.output else sys.stdout
    w = csv.DictWriter(out, fieldnames=fields)
    w.writeheader()
    w.writerows(kept)
    print(f"Removed {len(rows) - len(kept)} duplicate rows, kept {len(kept)}.", file=sys.stderr)


if __name__ == "__main__":
    main()
