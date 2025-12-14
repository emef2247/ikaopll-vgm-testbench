#!/usr/bin/env python3
import sys
import wave
import struct

def load_acc_values(path):
    """samples_acc.txt から ACC 値だけを読み込む。
    - 行が 1 列: その値だけを読む
    - 行が 2 列以上: 先頭の列を値として読む
    - 'x' など非数値はスキップ
    """
    vals = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if not parts:
                continue
            try:
                v = int(parts[0])
            except ValueError:
                # 先頭列が数値でなければスキップ（例: "x 0"）
                print(f"[WARN] skip line {lineno}: {s}")
                continue
            vals.append(v)
    return vals

def normalize_to_int16(samples):
    if not samples:
        return []
    peak = max(abs(float(v)) for v in samples)
    if peak == 0:
        return [0] * len(samples)
    scale = 0.9 * 32767.0 / peak
    print(f"[INFO] peak={peak}, scale={scale}")
    return [int(round(v * scale)) for v in samples]

def write_wav(path, samples, fs):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(fs))
        data = b"".join(struct.pack("<h", max(-32768, min(32767, int(s))))
                        for s in samples)
        w.writeframes(data)

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} samples_acc.txt [out.wav] [Fs]")
        sys.exit(1)

    in_txt = sys.argv[1]
    out_wav = sys.argv[2] if len(sys.argv) >= 3 else "acc_raw_1M.wav"
    fs_out  = float(sys.argv[3]) if len(sys.argv) >= 4 else 1_000_000.0  # デフォルト 1 MHz

    vals = load_acc_values(in_txt)
    print(f"[INFO] loaded {len(vals)} ACC samples")

    int16_samples = normalize_to_int16(vals)
    write_wav(out_wav, int16_samples, fs_out)
    print(f"[INFO] wrote WAV: {out_wav} (Fs={fs_out} Hz)")

if __name__ == "__main__":
    main()

