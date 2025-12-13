#!/usr/bin/env python3
"""
Convert samples_mo.txt (one integer per DAC output) into a 16-bit mono WAV.

- samples_mo.txt には o_DAC_EN_MO が 1 のときの o_IMP_FLUC_SIGNED_MO が
  1 行に 1 サンプルずつ書かれている。
- o_IMP_FLUC_SIGNED_MO はほぼ一定周期 (~20,113,920 ps) で更新されているので、
  およそ 49.7 kHz でサンプリングされた 1ch 音声信号とみなせる。
- ここでは一切間引かず、「1 行 = 1 サンプル」のまま WAV に変換する。
- DC 除去後の最大振幅から、「16bit でクリップしない最大ゲイン」を自動計算する。
"""

import sys
import wave
import struct
from typing import List

# 推定サンプリングレート (~49.7 kHz 近辺で固定)
OUT_RATE = 49_720
MAX_I16 = 32767


def load_samples(txt_path: str) -> List[int]:
    samples: List[int] = []
    with open(txt_path, "r") as f:
        for lineno, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                val = int(s, 10)
            except ValueError:
                # Skip non-integer lines (e.g. 'x')
                continue
            samples.append(val)
    return samples


def center_dc(samples: List[int]) -> List[int]:
    """Remove DC offset (平均値) を引いて、AC 成分を中心にする。"""
    if not samples:
        return samples
    avg = sum(samples) / len(samples)
    return [int(s - avg) for s in samples]


def scale_to_int16(samples: List[int], gain: int) -> List[int]:
    """与えられた gain でスケーリングし、16bit にクリップする。"""
    out: List[int] = []
    for s in samples:
        v = s * gain
        if v > MAX_I16:
            v = MAX_I16
        elif v < -MAX_I16 - 1:
            v = -MAX_I16 - 1
        out.append(int(v))
    return out


def write_wav(wav_path: str, samples_16: List[int], sample_rate: int) -> None:
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)       # mono
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(sample_rate)
        for s in samples_16:
            wf.writeframes(struct.pack("<h", s))


def main(txt_path: str, wav_path: str) -> None:
    print("[DEBUG] txt_to_wav.py: no-decimation, ~50kHz, auto-gain version")

    samples = load_samples(txt_path)
    if not samples:
        print(f"[ERROR] No valid integer samples found in {txt_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Loaded {len(samples)} samples from {txt_path}")

    # 1) DC 除去
    samples_dc = center_dc(samples)
    if samples_dc:
        min_dc = min(samples_dc)
        max_dc = max(samples_dc)
        print(f"[DEBUG] DC-centered min={min_dc} max={max_dc}")
    else:
        min_dc = max_dc = 0

    # 2) 自動ゲイン計算（クリップしない最大値を狙う）
    peak = max(abs(min_dc), abs(max_dc))
    if peak == 0:
        # すべて同じ値 (完全な DC) の場合はゲインを 1 にしておく
        gain = 1
        print("[WARN] Peak amplitude is 0 after DC removal; using gain=1")
    else:
        gain = MAX_I16 // peak  # floor(32767 / peak)
    print(f"[INFO] Auto gain computed from peak={peak}: gain={gain}")

    # 3) 16bit にスケーリング
    samples_16 = scale_to_int16(samples_dc, gain=gain)
    if samples_16:
        print(f"[DEBUG] int16 min={min(samples_16)} max={max(samples_16)}")

    # 4) WAV 出力
    write_wav(wav_path, samples_16, OUT_RATE)

    duration_sec = len(samples_16) / float(OUT_RATE)
    print(f"[INFO] Wrote WAV: {wav_path}")
    print(f"[INFO] Duration ≈ {duration_sec:.3f} seconds at {OUT_RATE} Hz, gain={gain}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} samples.txt out.wav", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])