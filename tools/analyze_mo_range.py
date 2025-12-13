#!/usr/bin/env python3
import sys

def analyze_mo(path: str):
    mn = None
    mx = None
    cnt = 0

    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 2:
                print(f"[WARN] skip line {lineno}: {s}")
                continue
            try:
                v = int(parts[1])
            except ValueError:
                print(f"[WARN] skip line {lineno}: non-int -> {s}")
                continue
            cnt += 1
            if mn is None or v < mn:
                mn = v
            if mx is None or v > mx:
                mx = v

    if cnt == 0:
        print("[ERROR] no valid samples")
        return

    print(f"# file   : {path}")
    print(f"# count  : {cnt}")
    print(f"min MO   : {mn}")
    print(f"max MO   : {mx}")

def main():
    if len(sys.argv) >= 2:
        path = sys.argv[1]
    else:
        path = "samples_mo.txt"
    analyze_mo(path)

if __name__ == "__main__":
    main()

