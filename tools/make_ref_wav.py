#!/usr/bin/env python3
"""
make_ref_wav.py

Generate reference WAV files from IKAOPLL_vgm_tb.sv logs.

Inputs (produced by the testbench):
  - samples_mo.txt   : "dur_idx value time_ps"
  - samples_acc.txt  : "value" or "value time_ps" (leading 'x' lines ignored)

Outputs (by default):
  - mo_ref_44k1.wav      : Mo-based reference (duration-averaged, smoothed)
  - acc_ref_44k1.wav     : ACC-based reference (decimated from internal Fs)
"""

import sys
import wave
import struct
import math
from pathlib import Path


# ----------------------------------------------------------------------
# Helper: write int16 mono WAV
# ----------------------------------------------------------------------
def write_wav(path, samples, fs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(fs))
        data = b"".join(
            struct.pack("<h", max(-32768, min(32767, int(s))))
            for s in samples
        )
        w.writeframes(data)


def normalize_to_int16(samples):
    if not samples:
        return []
    peak = max(abs(float(v)) for v in samples)
    if peak == 0:
        return [0] * len(samples)
    scale = 0.9 * 32767.0 / peak
    print(f"[INFO] peak={peak}, scale={scale}")
    return [int(round(v * scale)) for v in samples]


# ----------------------------------------------------------------------
# Mo path: avg_mo_by_duration + avg_mo_to_wav 相当
# ----------------------------------------------------------------------
def load_avg_mo_by_duration_from_samples_mo(path):
    """
    samples_mo.txt: "dur_idx value time_ps"
    → duration idx ごとに value を平均する
    """
    per_dur = {}
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 2:
                print(f"[WARN] [Mo] skip line {lineno}: {s}")
                continue
            try:
                dur_idx = int(parts[0])
                mo_val  = int(parts[1])
            except ValueError:
                print(f"[WARN] [Mo] skip line {lineno}: {s}")
                continue
            if dur_idx not in per_dur:
                per_dur[dur_idx] = [0, 0]  # sum, cnt
            per_dur[dur_idx][0] += mo_val
            per_dur[dur_idx][1] += 1

    if not per_dur:
        return []

    max_idx = max(per_dur.keys())
    avg = []
    for i in range(max_idx + 1):
        if i in per_dur and per_dur[i][1] > 0:
            avg.append(per_dur[i][0] / per_dur[i][1])
        else:
            avg.append(0.0)
    print(f"[INFO] [Mo] durations with samples : {len(per_dur)}")
    print(f"[INFO] [Mo] first dur_idx: 0, last dur_idx: {max_idx}")
    return avg


def moving_average(samples, window):
    if window <= 1 or not samples:
        return samples[:]
    n = len(samples)
    out = [0.0] * n
    w = int(window)
    half = w // 2
    for i in range(n):
        start = max(0, i - half)
        end   = min(n - 1, i + half)
        length = end - start + 1
        acc = 0.0
        for j in range(start, end + 1):
            acc += samples[j]
        out[i] = acc / length
    return out


def make_mo_ref_wav(samples_mo_txt, out_wav="mo_ref_44k1.wav",
                    fs_out=44100.0, ma_window=15):
    avg = load_avg_mo_by_duration_from_samples_mo(samples_mo_txt)
    if not avg:
        print("[WARN] [Mo] no data, skip WAV generation")
        return
    print(f"[INFO] [Mo] loaded {len(avg)} averaged Mo samples")

    print(f"[INFO] [Mo] moving average window = {ma_window}")
    smoothed = moving_average(avg, ma_window)

    int16_samples = normalize_to_int16(smoothed)
    write_wav(out_wav, int16_samples, fs_out)
    print(f"[INFO] [Mo] wrote WAV: {out_wav} (Fs={fs_out} Hz)")


# ----------------------------------------------------------------------
# ACC path: acc_decimate_to_wav 相当
# ----------------------------------------------------------------------
def load_acc_values(path):
    """
    samples_acc.txt から ACC 値だけを読み込む。
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
                print(f"[WARN] [ACC] skip line {lineno}: {s}")
                continue
            vals.append(float(v))
    return vals


def moving_average_lpf(samples, window):
    """ACC 用の簡易 LPF（移動平均的）。"""
    if window <= 1 or not samples:
        return samples[:]
    n = len(samples)
    out = [0.0] * n
    w = int(window)
    half = w // 2

    for i in range(n):
        start = max(0, i - half)
        end   = min(n - 1, i + half)
        length = end - start + 1
        acc = 0.0
        for j in range(start, end + 1):
            acc += samples[j]
        out[i] = acc / length
    return out


def decimate(samples, factor):
    return samples[::factor]


def make_acc_ref_wav(samples_acc_txt,
                     out_wav="acc_ref_44k1.wav",
                     fs_int=1_600_000.0,
                     fs_out_target=44_100.0):
    vals = load_acc_values(samples_acc_txt)
    if not vals:
        print("[WARN] [ACC] no data, skip WAV generation")
        return
    print(f"[INFO] [ACC] loaded {len(vals)} ACC samples")

    decim = int(round(fs_int / fs_out_target))
    if decim < 1:
        decim = 1
    eff_fs_out = fs_int / decim
    print(f"[INFO] [ACC] Fs_int={fs_int} Hz, target Fs_out={fs_out_target} Hz")
    print(f"[INFO] [ACC] decimation factor={decim}, effective Fs_out={eff_fs_out} Hz")

    window = decim * 3
    print(f"[INFO] [ACC] moving-average window={window}")
    lp = moving_average_lpf(vals, window)

    dec = decimate(lp, decim)
    print(f"[INFO] [ACC] decimated samples: {len(dec)}")

    int16_samples = normalize_to_int16(dec)
    write_wav(out_wav, int16_samples, eff_fs_out)
    print(f"[INFO] [ACC] wrote WAV: {out_wav} (Fs={eff_fs_out} Hz)")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    # デフォルトのパス
    samples_mo = "samples_mo.txt"
    samples_acc = "samples_acc.txt"
    mo_wav = "mo_ref_44k1.wav"
    acc_wav = "acc_ref_44k1.wav"

    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print("Usage: make_ref_wav.py [samples_mo.txt] [samples_acc.txt]")
        print("  Defaults: samples_mo.txt, samples_acc.txt in current dir.")
        sys.exit(0)

    if len(sys.argv) >= 2:
        samples_mo = sys.argv[1]
    if len(sys.argv) >= 3:
        samples_acc = sys.argv[2]

    print(f"[INFO] using samples_mo:  {samples_mo}")
    print(f"[INFO] using samples_acc: {samples_acc}")

    # Mo-based ref WAV
    make_mo_ref_wav(samples_mo, mo_wav, fs_out=44100.0, ma_window=15)

    # ACC-based ref WAV
    make_acc_ref_wav(samples_acc, acc_wav,
                     fs_int=1_600_000.0,
                     fs_out_target=44_100.0)


if __name__ == "__main__":
    main()

