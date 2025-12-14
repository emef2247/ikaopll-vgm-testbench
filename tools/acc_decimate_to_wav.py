#!/usr/bin/env python3
import sys
import wave
import struct
import math

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
                print(f"[WARN] skip line {lineno}: {s}")
                continue
            vals.append(float(v))
    return vals

def fir_lowpass(samples, fs, cutoff_hz=15000.0, taps=129):
    """簡易 Hamming 窓 FIR LPF"""
    if not samples:
        return []
    fc = cutoff_hz / (fs / 2.0)  # 正規化カットオフ 0..1
    if fc >= 1.0:
        return samples[:]

    M = taps - 1
    h = []
    for n in range(taps):
        if n == M / 2:
            hn = 2 * fc
        else:
            x = math.pi * (n - M / 2)
            hn = math.sin(2 * fc * x) / x
        w = 0.54 - 0.46 * math.cos(2 * math.pi * n / M)  # Hamming window
        h.append(hn * w)
    # 正規化
    s = sum(h)
    h = [x / s for x in h]

    out = [0.0] * len(samples)
    for n in range(len(samples)):
        acc = 0.0
        for k in range(taps):
            idx = n - k
            if 0 <= idx < len(samples):
                acc += h[k] * samples[idx]
        out[n] = acc
    return out

def decimate(samples, factor):
    """単純な間引き（LPF 済み前提）"""
    return samples[::factor]

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
        print(f"Usage: {sys.argv[0]} samples_acc.txt [out.wav] [Fs_int] [Fs_out]")
        print("  Fs_int: internal sample rate (default 1_600_000 Hz)")
        print("  Fs_out: output sample rate  (default 44_100 Hz)")
        sys.exit(1)

    in_txt = sys.argv[1]
    out_wav = sys.argv[2] if len(sys.argv) >= 3 else "acc_decim_44k1.wav"
    Fs_int  = float(sys.argv[3]) if len(sys.argv) >= 4 else 1_600_000.0
    Fs_out  = float(sys.argv[4]) if len(sys.argv) >= 5 else 44_100.0

    vals = load_acc_values(in_txt)
    print(f"[INFO] loaded {len(vals)} ACC samples")
    if not vals:
        print("[ERROR] no samples")
        sys.exit(1)

    decim = int(round(Fs_int / Fs_out))
    if decim < 1:
        decim = 1
    eff_Fs_out = Fs_int / decim
    print(f"[INFO] Fs_int={Fs_int} Hz, target Fs_out={Fs_out} Hz")
    print(f"[INFO] decimation factor={decim}, effective Fs_out={eff_Fs_out} Hz")

    # LPF → 間引き
    lp = fir_lowpass(vals, Fs_int, cutoff_hz=min(18000.0, eff_Fs_out/2.5), taps=129)
    dec = decimate(lp, decim)
    print(f"[INFO] decimated samples: {len(dec)}")

    int16_samples = normalize_to_int16(dec)
    write_wav(out_wav, int16_samples, eff_Fs_out)
    print(f"[INFO] wrote WAV: {out_wav} (Fs={eff_Fs_out} Hz)")

if __name__ == "__main__":
    main()
