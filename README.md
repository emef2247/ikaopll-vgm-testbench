# ikaopll-vgm-testbench

Experimental YM2413 (OPLL) testbench using the IKAOPLL core and VGM/CSV playback.

This repository is a **standalone simulation playground** built on top of the original [IKAOPLL](https://github.com/ika-musume/IKAOPLL) core by Sehyeon Kim (Raki).  
It adds a SystemVerilog testbench that can:

- Drive the IKAOPLL YM2413 core with a realistic OPLL clock
- Replay register-write traces exported from MSX MSGDRV via openMSX as VGM → CSV
- Dump internal DAC signals to a text file or VCD for analysis and audio conversion

The goal is to **experimentally verify YM2413 behaviour** (including edge cases) and to prepare for integration into a VGM player / emulator.

> Note: This is **not** the official IKAOPLL repository.  
> The original core and documentation remain © Sehyeon Kim (Raki) and are used here under the BSD 2‑Clause License.

---

## Contents

- `src/IKAOPLL.v`, `src/IKAOPLL_modules/…`  
  Original IKAOPLL YM2413 core (unmodified).

- `src/IKAOPLL_tb.sv`  
  Original testbench shipped with IKAOPLL.

- `src/IKAOPLL_vgm_tb.sv`  
  New testbench for this project:
  - Generates a ~3.58 MHz EMUCLK matching the real YM2413 phiM
  - Applies reset according to `FAST_RESET` semantics
  - Issues bus writes using a task compatible with IKAOPLL’s bus timing
  - Logs DAC outputs for waveform / audio inspection
  - (Planned) Drives the core from VGM‑derived CSV files

- `tests/*.vgm.csv`  
  YM2413 register traces captured from **MSX MSGDRV** running under **openMSX**, exported as VGM and converted to CSV.  
  These sequences contain:
  - Various scales and test patterns
  - Rhythm mode toggling
  - Patch changes, legato, retrigger tests
  - Redundant register writes, block boundary checks, etc.

- `doc/tb_design_plan.md`  
  Design notes for the new VGM‑oriented testbench.

- `docs/…`  
  Datasheets, application manuals and reference images for YM2413.

---

## Current status

At this stage:

- The IKAOPLL core instantiates and runs under **iverilog**.
- A new testbench (`IKAOPLL_vgm_tb.sv`) has been created with:
  - Realistic OPLL clock generation
  - Synchronous reset handling
  - A bus write task adapted from the original testbench (iverilog‑compatible)
  - VCD dumping for waveform inspection
  - Console logging of `o_DAC_EN_MO` and `o_IMP_FLUC_SIGNED_MO` to verify sound activity

Next planned steps:

1. Add a file logger that writes DAC samples (e.g. `IMP_FLUC_MO`) to a text file.
2. Implement CSV‑driven register playback:
   - Parse `tests/ym2413_*.vgm.csv`
   - Convert VGM delays to EMUCLK cycles
   - Issue address/data writes accordingly
3. Provide helper scripts to convert logged samples into 44.1 kHz WAV for listening tests.

---

## Building and running with iverilog

From the repository root:

```bash
# Build (SystemVerilog, iverilog)
iverilog -g2012 -o ikaopll_vgm_tb.vvp \
  src/IKAOPLL.v \
  src/IKAOPLL_modules/IKAOPLL_*.v \
  src/IKAOPLL_vgm_tb.sv

# Run
vvp ikaopll_vgm_tb.vvp
```

This will:

- Produce `ikaopll_vgm_tb.vcd` for waveform inspection (e.g. with GTKWave).
- Print DAC activity to stdout, for example:

```text
VCD info: dumpfile ikaopll_vgm_tb.vcd opened for output.
[321264] DAC_EN_MO=1 IMP_FLUC_MO=1 (0x001)
…
```

You can open the VCD with:

```bash
gtkwave ikaopll_vgm_tb.vcd &
```

and inspect signals such as:

- `IC_n`, `EMUCLK`
- `CS_n`, `WR_n`, `A0`, `DIN`
- `o_DAC_EN_MO`, `o_IMP_FLUC_SIGNED_MO`
- (optionally) internal registers via the `dut` hierarchy

---

## License and attribution

- The IKAOPLL core (`src/IKAOPLL.v`, `src/IKAOPLL_modules/…`) and original documentation are:
  - © 2024 Sehyeon Kim (Raki)
  - Licensed under the **BSD 2‑Clause License** (see [LICENSE](LICENSE)).

- This repository’s additional files (testbench, CSV tests, docs) are intended to be released under the **same BSD 2‑Clause License** for compatibility and simplicity.

If you use this project, please also credit the original IKAOPLL author and repository:

- [IKAOPLL on GitHub](https://github.com/ika-musume/IKAOPLL)

---