#!/usr/bin/env python3
import sys
import wave
import struct

def load_int_list(path):
    vals = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                v = int(s)
            except ValueError:
                print(f"[WARN] skip line {lineno}: {s}")
                continue
            vals.append(v)
    return vals

def normalize_to_int16(vals):
    if not vals:
        return []
    peak = max(abs(v) for v in vals)
    if peak == 0:
        return [0]*len(vals)
    scale = 0.9 * 32767.0 / peak
    print(f"[INFO] peak={peak}, scale={scale}")
    return [int(round(v*scale)) for v in vals]

def write_wav(path, samples, fs):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)      # int16
        w.setframerate(int(fs))
        data = b"".join(struct.pack("<h", s) for s in samples)
        w.writeframes(data)

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} samples_acc.txt [out.wav] [Fs]")
        sys.exit(1)

    in_txt = sys.argv[1]
    if len(sys.argv) >= 3:
        out_wav = sys.argv[2]
    else:
        out_wav = "acc_48k.wav"

    if len(sys.argv) >= 4:
        Fs = float(sys.argv[3])
    else:
        Fs = 48000.0  # デフォルト 48kHz

    vals = load_int_list(in_txt)
    if not vals:
        print("[ERROR] no samples loaded")
        sys.exit(1)

    print(f"[INFO] loaded {len(vals)} ACC samples")
    int16_vals = normalize_to_int16(vals)
    write_wav(out_wav, int16_vals, Fs)
    print(f"[INFO] wrote WAV: {out_wav} (Fs={Fs} Hz)")

if __name__ == "__main__":
    main()

