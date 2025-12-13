#!/usr/bin/env python3
import sys
from collections import defaultdict

def load_and_average(path: str):
    # dur_idx ごとに sum と count を蓄積
    acc = defaultdict(lambda: {"sum": 0.0, "count": 0})

    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 2:
                print(f"[WARN] skip line {lineno}: {s}")
                continue

            dur_str = parts[0]
            val_str = parts[1]

            try:
                d = int(dur_str)
                v = int(val_str)
            except ValueError:
                print(f"[WARN] skip line {lineno}: non-int -> {s}")
                continue

            acc[d]["sum"] += v
            acc[d]["count"] += 1

    # dur_idx 昇順で平均値のリストを作る
    if not acc:
        print("[ERROR] no valid samples")
        return []

    keys = sorted(acc.keys())
    avg_vals = []
    for d in keys:
        c = acc[d]["count"]
        if c == 0:
            avg_vals.append(0.0)
        else:
            avg_vals.append(acc[d]["sum"] / c)

    print(f"[INFO] durations with samples : {len(keys)}")
    print(f"[INFO] first dur_idx: {keys[0]}, last dur_idx: {keys[-1]}")
    return avg_vals

def main():
    if len(sys.argv) >= 2:
        in_path = sys.argv[1]
    else:
        in_path = "samples_mo.txt"

    avg_vals = load_and_average(in_path)
    if not avg_vals:
        return

    # 生の平均値をテキストでダンプ（デバッグ用途）
    out_txt = "avg_mo_by_duration.txt"
    with open(out_txt, "w") as f:
        for x in avg_vals:
            f.write(f"{x}\n")

    print(f"[INFO] wrote {len(avg_vals)} averaged samples to {out_txt}")

if __name__ == "__main__":
    main()

