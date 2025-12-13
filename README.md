# IKAOPLL

IKAOPLL is a cycle-accurate, fully-synchronous YM2413 (OPLL) core written in Verilog.

This repository also contains a small testbench infrastructure and tools to:

- Convert YM2413 VGM files to a simple CSV format
- Convert that CSV to a Verilog include file (`.vh`) that drives the IKAOPLL bus
- Run simulations and export DAC‑related signals as text
- Convert the text samples to WAV for listening / analysis

The Japanese version of this document is available in [README.ja.md](README.ja.md).

---

## Repository layout

- `src/IKAOPLL.v`, `src/IKAOPLL_modules/…`  
  Main IKAOPLL core and submodules
- `IKAOPLL_vgm_tb.sv`  
  Testbench that plays a VGM‑derived pattern into IKAOPLL and dumps DAC‑related outputs
- `tools/vgm_to_ym2413_csv.py`  
  **Python VGM→CSV converter** for YM2413 commands (used for all tests)
- `tools/vgm_csv_to_vh.py`  
  CSV→Verilog include converter – generates `IKAOPLL_write(...)` calls
- `tools/txt_to_wav.py`  
  Legacy/simple text‑to‑WAV converter for `samples_mo.txt`
- **Waveform analysis helpers**
  - `tools/avg_mo_by_duration.py` – average `IMP_FLUC_MO` per duration index  
  - `tools/avg_mo_to_wav.py` – convert the averaged series to WAV (with simple smoothing)  
  - `tools/acc_to_wav.py` – convert `ACC_SIGNED` samples to WAV  
  - `tools/analyze_mo_range.py` – min/max of `IMP_FLUC_MO` from `samples_mo.txt`  
  - `tools/analyze_duration.py` – basic statistics of `durations.txt`
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
  - Hex string such as `"0E"` or `"20"`

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
- Play the VGM‑derived bus pattern into IKAOPLL (with OPLL‑spec wait times enforced in the TB)
- Log:
  - `IMP_FLUC_SIGNED_MO` to `samples_mo.txt`
  - duration boundaries (from `ACC_STRB`) to `durations.txt`
  - `ACC_SIGNED` to `samples_acc.txt`
- Finish when the pattern completes

---

## Converting simulation logs to WAV

There are two main pipelines for listening to the simulated sound:

- **Mo-based** (using `IMP_FLUC_MO` averaged per duration)  
  – gives a stable, per‑duration envelope‑like signal  
- **ACC-based** (using `ACC_SIGNED` directly)  
  – exposes the mixed accumulator output

### 1. Mo-based WAV (recommended for quick checking)

1. **Average Mo per duration**

   ```bash
   python3 tools/avg_mo_by_duration.py samples_mo.txt
   ```

   This produces `avg_mo_by_duration.txt`, which contains one averaged value per duration index.

2. **Convert the averaged series to WAV**

   ```bash
   # 48 kHz, simple moving-average smoothing window = 15
   python3 tools/avg_mo_to_wav.py avg_mo_by_duration.txt mo_avg_ma15_48k.wav 48000 15

   # 44.1 kHz version
   python3 tools/avg_mo_to_wav.py avg_mo_by_duration.txt mo_avg_ma15_44k1.wav 44100 15
   ```

   Notes:

   - The last argument is the moving-average window length (odd number recommended: 5, 9, 15, …).  
     Larger windows reduce “grainy” noise but blur fast attacks.
   - These WAVs are useful to verify:
     - Overall length / tempo
     - Rough pitch movement
     - Whether multiple notes are being generated

### 2. ACC-based WAV (experimental)

If `IKAOPLL_vgm_tb.sv` is built with ACC logging enabled, the testbench will also write `samples_acc.txt`, one integer sample per `ACC_STRB` pulse.

You can turn this directly into a WAV file:

```bash
# 48 kHz
python3 tools/acc_to_wav.py samples_acc.txt acc_48k.wav

# 44.1 kHz
python3 tools/acc_to_wav.py samples_acc.txt acc_44k1.wav 44100
```

This path is closer to the mixed DAC input, but the resulting audio can sound noisy or sparse depending on how often `ACC_STRB` is asserted and how you interpret it. It is mainly intended for analysis / experimentation.

### 3. Legacy direct Mo→WAV path

For historical reasons, there is also a simple “raw text to WAV” helper:

```bash
python3 tools/txt_to_wav.py samples_mo.txt out.wav
```

This treats each `IMP_FLUC_MO` sample as an equally-spaced time series with a fixed sample rate. The Mo‑averaged pipeline above tends to give more stable results for musical tests.

---

## Small analysis helpers

- **`tools/analyze_mo_range.py`**

  Compute min/max of `IMP_FLUC_MO` from `samples_mo.txt`:

  ```bash
  python3 tools/analyze_mo_range.py samples_mo.txt
  ```

- **`tools/analyze_duration.py`**

  Inspect `durations.txt` (duration statistics, estimated sampling rate if you take one sample per duration):

  ```bash
  python3 tools/analyze_duration.py durations.txt
  ```

These are optional, but useful when iterating on the testbench or trying to understand timing behaviour.