# IKAOPLL

IKAOPLL is a cycle-accurate, fully-synchronous YM2413 (OPLL) core written in Verilog.

This repository also contains a small testbench infrastructure and tools to:

- Convert YM2413 VGM files to a simple CSV format
- Convert that CSV to a Verilog include file (`.vh`) that drives the IKAOPLL bus
- Run simulations and export DAC output (`samples_mo.txt`)
- Convert the text samples to WAV

The Japanese version of this document is available in [README.ja.md](README.ja.md).

---

## Repository layout

- `src/IKAOPLL.v`, `src/IKAOPLL_modules/…`  
  Main IKAOPLL core and submodules
- `IKAOPLL_vgm_tb.sv`  
  Testbench that plays a VGM‑derived pattern into IKAOPLL and dumps DAC output
- `tools/vgm_to_ym2413_csv.py`  
  **Python VGM→CSV converter** for YM2413 commands (used for all tests)
- `tools/vgm_csv_to_vh.py`  
  CSV→Verilog include converter – generates `IKAOPLL_write(...)` calls
- `tools/txt_to_wav.py`  
  Simple text‑to‑WAV converter for `samples_mo.txt`
- `tests/*.vgm`  
  YM2413 VGM test patterns
- `tests/*.vgm.csv`  
  CSV generated from the VGM files by `vgm_to_ym2413_csv.py`

---

## YM2413 VGM → CSV (`tools/vgm_to_ym2413_csv.py`)

All test CSV files (and any new ones you create) are generated with the Python script:

```bash
python3 tools/vgm_to_ym2413_csv.py path/to/file.vgm
```

This produces `path/to/file.vgm.csv` with the following format:

```text
delay,reg,data
0,01,0E
0,00,20
983,01,10
0,00,00
...
```

Where:

- **delay**
  - Unsigned integer
  - Difference of VGM sample counters (`timestamp.current_sample`) at 44.1 kHz
  - Unit is “44100 Hz PCM samples” (VGM’s standard rate)
  - Treated as **“wait-before”** in the testbench
- **reg**
  - `"01"` → address phase (A0 = 0)
  - `"00"` → data phase (A0 = 1)
- **data**
  - Hex string such as `"0E"` or `"0x20"`

Examples (as used in this repo):

```bash
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_3ch_test.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_block_boundary.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_chords_mix.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_highlow_range.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_legato_patch_mix.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_patch_change_midnote.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_redundant_fnum_writes.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_release_retrigger.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_retrigger.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_rhythm_mode_basic.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_rhythm_mode_toggle.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_scale_chromatic.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_scale_rom1.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_short_pulses.vgm
python3 tools/vgm_to_ym2413_csv.py tests/ym2413_volume_sweep.vgm
```

---

## CSV → Verilog include (`tools/vgm_csv_to_vh.py`)

`vgm_csv_to_vh.py` converts the CSV into a `.vh` file that the testbench includes.

Usage:

```bash
python3 tools/vgm_csv_to_vh.py tests/ym2413_scale_chromatic.vgm.csv \
  tests/ym2413_scale_chromatic.vh
```

This generates lines like:

```verilog
// Auto-generated from ym2413_scale_chromatic.vgm.csv
// Each # delay is a VGM *delta* (per-row delay) converted to 10ps ticks.

#2267532 IKAOPLL_write(1'b0, 8'h0E, phiMref, CS_n, WR_n, A0, DIN);
#0       IKAOPLL_write(1'b1, 8'h20, phiMref, CS_n, WR_n, A0, DIN);
#222218136 IKAOPLL_write(1'b0, 8'h10, phiMref, CS_n, WR_n, A0, DIN);
#0         IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
...
```

Important details:

- `timescale 10ps/10ps` is assumed (must match `IKAOPLL_vgm_tb.sv`).
- EMUCLK frequency is 3.579545 MHz.
- Each `#<ticks>` is a **per-row delay**:  
  `ticks = delay * TICKS_PER_SAMPLE`
- Verilog’s `#` is a **relative** delay, so feeding the CSV’s per-row delta is the correct way to reproduce VGM timing.

---

## Running the VGM testbench

1. Generate CSVs from VGM (if you have your own files):

   ```bash
   python3 tools/vgm_to_ym2413_csv.py tests/your_vgm.vgm
   ```

2. Convert CSV to `.vh`:

   ```bash
   python3 tools/vgm_csv_to_vh.py tests/your_vgm.vgm.csv tests/your_vgm.vh
   ```

3. Make sure the testbench includes the right `.vh`:

   ```systemverilog
   `include "tests/your_vgm.vh"
   ```

4. Build and run the testbench (example with Icarus Verilog):

   ```bash
   iverilog -g2012 -o ikaopll_vgm_tb.vvp \
     src/IKAOPLL.v src/IKAOPLL_modules/IKAOPLL_*.v IKAOPLL_vgm_tb.sv

   vvp ikaopll_vgm_tb.vvp
   ```

The testbench will:

- Apply reset
- Play the VGM‑derived bus pattern into IKAOPLL
- Log the DAC output (`IMP_FLUC_SIGNED_MO`) into `samples_mo.txt`
- Finish when the pattern completes

---

## Converting `samples_mo.txt` to WAV

Once the simulation finishes, convert the logged samples to WAV:

```bash
python3 tools/txt_to_wav.py samples_mo.txt out.wav
```

This lets you listen to the simulated audio from the IKAOPLL core.

---