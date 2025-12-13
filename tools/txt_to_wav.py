#!/usr/bin/env python3
"""
Convert a text file of integer samples (one per line) into a 16-bit mono WAV.

- Intended for ikaopll-vgm-testbench's samples_mo.txt
- Lines that are not valid integers (e.g. 'x') are skipped.
- 9-bit-ish values are scaled up to 16-bit with a simple fixed factor.

Usage:
    python3 tools/txt_to_wav.py samples_mo.txt out.wav
"""

import sys
import wave
import struct
from typing import List


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
                # Skip non-integer lines (e.g. 'x' from X-propagation)
                # You can uncomment this for debugging:
                # print(f"Skipping non-integer line {lineno}: {s}", file=sys.stderr)
                continue
            samples.append(val)
    return samples


def scale_to_int16(samples: List[int], gain: int = 128) -> List[int]:
    """
    Scale raw samples (approx. 9-bit range) to 16-bit signed range.
    gain: simple linear gain factor, default 128 ~= 2^(16-9)
    """
    out: List[int] = []
    for s in samples:
        v = s * gain
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        out.append(int(v))
    return out


def write_wav(wav_path: str, samples_16: List[int], sample_rate: int = 44100) -> None:
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)       # mono
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(sample_rate)
        for s in samples_16:
            wf.writeframes(struct.pack("<h", s))


def main(txt_path: str, wav_path: str) -> None:
    samples = load_samples(txt_path)
    if not samples:
        print(f"[ERROR] No valid integer samples found in {txt_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Loaded {len(samples)} samples from {txt_path}")

    samples_16 = scale_to_int16(samples)
    write_wav(wav_path, samples_16)

    print(f"[INFO] Wrote WAV: {wav_path}")
    print(f"[INFO] Duration ≈ {len(samples_16) / 44100.0:.3f} seconds at 44100 Hz")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} samples.txt out.wav", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

