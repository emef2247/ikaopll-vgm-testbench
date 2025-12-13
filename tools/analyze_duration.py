#!/usr/bin/env python3
import sys
import statistics as stats
from pathlib import Path

def analyze_durations(path: str):
    p = Path(path)
    if not p.is_file():
        print(f"[ERROR] durations file not found: {p}")
        return

    durations = []
    start0 = None
    end_last = None

    with p.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 3:
                # 2列しか無い・ゴミ行などはスキップしつつ警告
                print(f"[WARN] skip line {lineno}: expected 3 cols, got {len(parts)} -> {line}")
                continue

            idx_str, s_str, e_str = parts[:3]
            try:
                idx = int(idx_str)
                s   = int(s_str)
                e   = int(e_str)
            except ValueError:
                print(f"[WARN] skip line {lineno}: non-integer field -> {line}")
                continue

            if start0 is None:
                start0 = s
            end_last = e
            durations.append(e - s)

    if not durations:
        print("[ERROR] no valid duration entries found.")
        return

    print(f"# file      : {p}")
    print(f"# intervals : {len(durations)}")
    print(f"min Δt [ps]: {min(durations)}")
    print(f"max Δt [ps]: {max(durations)}")
    print(f"mean Δt[ps]: {stats.mean(durations):.3f}")
    if len(durations) > 1:
        print(f"stdev[ps]  : {stats.pstdev(durations):.3f}")

    if start0 is not None and end_last is not None:
        total_time_ps = end_last - start0
        total_time_s  = total_time_ps * 1e-12
        print(f"total time [ps]: {total_time_ps}")
        print(f"total time [s ]: {total_time_s:.9f}")

        # 「Duration ごと 1 サンプル」と仮定したときの実効 Fs
        N = len(durations)
        if total_time_s > 0:
            fs = N / total_time_s
            print(f"effective Fs if 1 sample/Duration: {fs:.3f} Hz")

def main():
    # 引数があればそれを使う。無ければデフォルト "durations.txt"
    if len(sys.argv) >= 2:
        path = sys.argv[1]
    else:
        path = "durations.txt"
    analyze_durations(path)

if __name__ == "__main__":
    main()

