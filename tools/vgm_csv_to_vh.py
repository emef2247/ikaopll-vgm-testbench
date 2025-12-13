#!/usr/bin/env python3
"""
Convert YM2413 VGM CSV (delay,reg,data) into a Verilog include file (.vh)
containing a sequence of IKAOPLL_write(...) calls with appropriate #delays.

Assumptions about the CSV:

- CSV format (from record_csv in vgm_helpers.c):

    delay,reg,data

  where:

  - delay:
      - Unsigned integer
      - Difference of VGM sample counters (timestamp.current_sample) at 44.1 kHz
      - 単位は「44100Hz の PCM サンプル数」
  - reg:
      - "01" : address phase (A0=0)
      - "00" : data phase    (A0=1)
  - data:
      - Hex string like "0E" or "0x20"

Conversion policy:

- Treat delay as "wait-before" in VGM samples.
- For each CSV row, convert *that row's delay* to Verilog #ticks:

    ticks = delay * TICKS_PER_SAMPLE

  and then emit:

    #<ticks> IKAOPLL_write(1'bX, 8'hYY, phiMref, CS_n, WR_n, A0, DIN);

  where 1'bX is 0 for address (reg=="01"), 1 for data (reg=="00").

- Note:
  - We NO LONGER use the accumulated absolute VGM time for #.
  - Verilog の `#` は「相対待ち」なので、CSV の差分 delay をそのまま使うのが正しい。
  - 結果として、テストベンチ上の時間 = Σ(delay) / 44100 秒 ＋ バス書き込みに要する数 µs/コマンド となる。

Timing model (must match IKAOPLL_vgm_tb.sv):

- `timescale 10ps/10ps`
- EMUCLK frequency: 3.579545 MHz
- EMUCLK period: 1 / 3_579_545 s
- EMUCLK ticks per period: 27,936 (10ps ticks)
- VGM sample rate: 44,100 Hz

Therefore:

- EMUCLK cycles per 1 VGM sample  ~= 3_579_545 / 44_100 ≈ 81.2
- TICKS_PER_SAMPLE = round(EMUCLK_PERIOD_TICKS * EMUCLK_HZ / VGM_RATE)
"""

import sys
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Clock / time parameters (must match IKAOPLL_vgm_tb.sv)
# ---------------------------------------------------------------------------
EMUCLK_HZ = 3_579_545.0       # EMUCLK frequency (Hz)
VGM_RATE  = 44_100.0          # VGM sample rate (Hz); CSV delay unit
TIMESCALE_PS = 10.0           # `timescale 10ps/10ps` → 10 picoseconds per tick

# EMUCLK 1 周期あたりのシミュレーション tick 数（10ps 単位）
EMUCLK_PERIOD_S = 1.0 / EMUCLK_HZ
EMUCLK_TICKS = int(round(EMUCLK_PERIOD_S / (TIMESCALE_PS * 1e-12)))
# 実際の TB では half-period #13968 → full period 27936 を前提にしているので上書き
EMUCLK_TICKS = 27_936

# 1 サンプル (1/44100 s) あたりの EMUCLK 周期数
EMU_PER_SAMPLE = EMUCLK_HZ / VGM_RATE          # ≈ 81.2

# 1 サンプルあたりのシミュレーション tick 数
TICKS_PER_SAMPLE = int(round(EMU_PER_SAMPLE * EMUCLK_TICKS))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_hex_byte(s: str) -> int:
    """Parse a hex byte from '0E' or '0x0E' → int 0x0E."""
    s = s.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s, 16)


def reg_is_addr(reg_field: str) -> bool:
    """
    CSV reg field:
      - "01" → address (A0 = 0)
      - "00" → data    (A0 = 1)
    """
    return reg_field.strip() == "01"


def main(argv):
    if len(argv) != 3:
        print(f"Usage: {argv[0]} <input.csv> <output.vh>", file=sys.stderr)
        return 1

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    if not in_path.exists():
        print(f"[ERROR] Input CSV not found: {in_path}", file=sys.stderr)
        return 1

    # Open files
    with in_path.open(newline="") as f_in, out_path.open("w") as f_out:
        reader = csv.reader(f_in)

        # Header skip (expects first line like: delay,reg,data)
        header = next(reader, None)
        if header is None:
            print("[ERROR] Empty CSV.", file=sys.stderr)
            return 1

        f_out.write("// Auto-generated from %s\n" % in_path.name)
        f_out.write("// timescale: 10ps; EMUCLK ~= 3.579545MHz\n")
        f_out.write("// Each # delay is a VGM *delta* (per-row delay) converted to 10ps ticks.\n\n")

        total_vgm_delay = 0      # accumulated delay in VGM samples (for info only)
        total_ticks     = 0      # accumulated ticks (for info only)

        for lineno, row in enumerate(reader, start=2):
            if len(row) < 3:
                print(f"[WARN] Line {lineno}: expected 3 columns, got {len(row)}", file=sys.stderr)
                continue

            delay_str, reg_str, data_str = row[0].strip(), row[1].strip(), row[2].strip()
            if delay_str == "":
                delay = 0
            else:
                try:
                    delay = int(delay_str)
                except ValueError:
                    print(f"[WARN] Line {lineno}: invalid delay '{delay_str}', treating as 0", file=sys.stderr)
                    delay = 0

            # VGM 累積サンプル数（参考情報用）
            total_vgm_delay += delay

            try:
                data_val = parse_hex_byte(data_str)
            except ValueError:
                print(f"[WARN] Line {lineno}: invalid data '{data_str}', skipping", file=sys.stderr)
                continue

            is_addr = reg_is_addr(reg_str)
            a0_bit = "1'b0" if is_addr else "1'b1"

            # この行の delay（サンプル差分） → 10ps tick に変換
            ticks = delay * TICKS_PER_SAMPLE
            total_ticks += ticks

            # Emit Verilog line
            # 例: #2262816 IKAOPLL_write(1'b0, 8'h0E, phiMref, CS_n, WR_n, A0, DIN);
            f_out.write(
                f"#{ticks} IKAOPLL_write({a0_bit}, 8'h{data_val:02X}, phiMref, CS_n, WR_n, A0, DIN);\n"
            )

    print(f"[INFO] Wrote Verilog pattern: {out_path}")
    print(f"[INFO] VGM total delay  = {total_vgm_delay} samples (~{total_vgm_delay / VGM_RATE:.3f} s)")
    print(f"[INFO] Sum of #ticks    = {total_ticks} ticks (~{total_ticks * TIMESCALE_PS * 1e-12:.3f} s at 10ps/tick)")
    print(f"[INFO] TICKS_PER_SAMPLE = {TICKS_PER_SAMPLE} (EMUCLK_TICKS={EMUCLK_TICKS}, EMU_PER_SAMPLE={EMU_PER_SAMPLE:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))