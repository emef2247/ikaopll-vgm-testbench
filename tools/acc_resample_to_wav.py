#!/usr/bin/env python3
import sys
import wave
import struct

def load_acc_with_time(path):
    vals = []
    times = []
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
                v = int(parts[0])
                t_ps = int(parts[1])  # ps
            except ValueError:
                print(f"[WARN] skip line {lineno}: {s}")
                continue
            vals.append(v)
            times.append(t_ps * 1e-12)  # ps -> s
    return vals, times

def estimate_internal_fs(times):
    if len(times) < 2:
        return None
    dt = [t1 - t0 for t0, t1 in zip(times[:-1], times[1:]) if t1 > t0]
    if not dt:
        return None
    avg_dt = sum(dt) / len(dt)
    return 1.0 / avg_dt

def resample_linear(vals, times, fs_out):
    """不等間隔サンプル(vals,times)を線形補間で fs_out へリサンプリング"""
    if not vals:
        return []
    t_start = times[0]
    t_end   = times[-1]
    n_out   = int((t_end - t_start) * fs_out)
    if n_out <= 0:
        return []

    out = []
    cur_idx = 0
    for i in range(n_out):
        t = t_start + i / fs_out
        # t を挟む2点を探す
        while cur_idx + 1 < len(times) and times[cur_idx + 1] < t:
            cur_idx += 1
        if cur_idx + 1 >= len(times):
            out.append(vals[-1])
            continue
        t0, t1 = times[cur_idx], times[cur_idx + 1]
        v0, v1 = vals[cur_idx], vals[cur_idx + 1]
        if t1 == t0:
            out.append(float(v0))
        else:
            alpha = (t - t0) / (t1 - t0)
            out.append(v0 + alpha * (v1 - v0))
    return out

def fir_lowpass(samples, fs, cutoff_hz=12000.0, taps=101):
    """簡易 Hamming 窓 FIR LPF"""
    import math
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
        print(f"Usage: {sys.argv[0]} samples_acc.txt [out.wav] [Fs_out]")
        sys.exit(1)

    in_txt = sys.argv[1]
    out_wav = sys.argv[2] if len(sys.argv) >= 3 else "acc_resampled_44k1.wav"
    fs_out  = float(sys.argv[3]) if len(sys.argv) >= 4 else 44100.0

    vals, times = load_acc_with_time(in_txt)
    print(f"[INFO] loaded {len(vals)} ACC samples")
    fs_int = estimate_internal_fs(times)
    if fs_int is None:
        print("[ERROR] failed to estimate internal Fs")
        sys.exit(1)
    print(f"[INFO] estimated internal Fs ≈ {fs_int:.3f} Hz")

    pcm = resample_linear(vals, times, fs_out)
    print(f"[INFO] resampled to {len(pcm)} samples at {fs_out} Hz")

    pcm_lp = fir_lowpass(pcm, fs_out, cutoff_hz=12000.0, taps=101)
    int16_samples = normalize_to_int16(pcm_lp)
    write_wav(out_wav, int16_samples, fs_out)
    print(f"[INFO] wrote WAV: {out_wav} (Fs={fs_out} Hz)")

if __name__ == "__main__":
    main()

