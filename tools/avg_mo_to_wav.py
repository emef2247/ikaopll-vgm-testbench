#!/usr/bin/env python3
import sys
import wave
import struct

def load_avg_samples(path: str):
    vals = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                v = float(s)
            except ValueError:
                print(f"[WARN] skip line {lineno}: {s}")
                continue
            vals.append(v)
    return vals

def moving_average(vals, win):
    """単純移動平均。win は奇数推奨（3,5,7,...）。"""
    if win <= 1:
        return vals
    half = win // 2
    n = len(vals)
    out = []
    for i in range(n):
        s = max(0, i - half)
        e = min(n, i + half + 1)
        out.append(sum(vals[s:e]) / (e - s))
    return out

def normalize_to_int16(vals):
    if not vals:
        return []

    peak = max(abs(v) for v in vals)
    if peak == 0:
        return [0] * len(vals)

    scale = 0.9 * 32767.0 / peak
    print(f"[INFO] peak={peak}, scale={scale}")
    return [int(round(v * scale)) for v in vals]

def write_wav(path: str, samples, fs: int):
    with wave.open(path, "wb") as w:
        nch = 1
        sampwidth = 2  # int16
        w.setnchannels(nch)
        w.setsampwidth(sampwidth)
        w.setframerate(fs)

        data = b"".join(struct.pack("<h", int(s)) for s in samples)
        w.writeframes(data)

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} avg_mo_by_duration.txt [out.wav] [Fs] [win]")
        sys.exit(1)

    in_txt = sys.argv[1]
    if len(sys.argv) >= 3:
        out_wav = sys.argv[2]
    else:
        out_wav = "mo_avg_48k_ma5.wav"

    if len(sys.argv) >= 4:
        Fs = float(sys.argv[3])
    else:
        Fs = 48000.0  # デフォルト 48kHz

    if len(sys.argv) >= 5:
        win = int(sys.argv[4])
    else:
        win = 5  # デフォルト窓長

    vals = load_avg_samples(in_txt)
    if not vals:
        print("[ERROR] no samples loaded")
        sys.exit(1)

    print(f"[INFO] loaded {len(vals)} averaged samples")
    print(f"[INFO] moving average window = {win}")
    smooth = moving_average(vals, win)

    int16_vals = normalize_to_int16(smooth)
    write_wav(out_wav, int16_vals, int(Fs))
    print(f"[INFO] wrote WAV: {out_wav} (Fs={Fs} Hz)")

if __name__ == "__main__":
    main()

