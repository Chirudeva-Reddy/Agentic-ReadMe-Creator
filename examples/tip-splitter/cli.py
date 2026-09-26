"""tip-splitter: split a bill between friends, tip included."""
import argparse


def split(total: float, people: int, tip_pct: float = 15.0) -> float:
    if people < 1:
        raise ValueError("people must be >= 1")
    return round(total * (1 + tip_pct / 100) / people, 2)


def main() -> None:
    p = argparse.ArgumentParser(description="Split a restaurant bill fairly, tip included.")
    p.add_argument("total", type=float, help="bill total before tip")
    p.add_argument("people", type=int, help="number of people paying")
    p.add_argument("--tip", type=float, default=15.0, help="tip percent (default 15)")
    a = p.parse_args()
    print(f"Each person pays {split(a.total, a.people, a.tip):.2f}")


if __name__ == "__main__":
    main()
