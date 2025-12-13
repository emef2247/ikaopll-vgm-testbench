# IKAOPLL

IKAOPLL は、Verilog で実装したサイクル精度の YM2413 (OPLL) コアです。

このリポジトリには、以下のようなテストベンチ／ツール類も含まれています。

- YM2413 向け VGM ファイルをシンプルな CSV に変換するスクリプト
- CSV から IKAOPLL 用の Verilog インクルードファイル (`.vh`) を生成するスクリプト
- テストベンチで VGM 由来のパターンを流して DAC 出力 (`samples_mo.txt`) を記録
- テキストサンプルを WAV に変換するスクリプト

英語版 README は [README.md](README.md) を参照してください。

---

## リポジトリ構成

- `src/IKAOPLL.v`, `src/IKAOPLL_modules/…`  
  IKAOPLL 本体とサブモジュール
- `IKAOPLL_vgm_tb.sv`  
  VGM 由来のパターンを IKAOPLL に流して DAC 出力を記録するテストベンチ
- `tools/vgm_to_ym2413_csv.py`  
  **YM2413 用 VGM→CSV 変換スクリプト**（すべてのテストで使用）
- `tools/vgm_csv_to_vh.py`  
  CSV→Verilog インクルード変換スクリプト（`IKAOPLL_write(...)` 呼び出し列を生成）
- `tools/txt_to_wav.py`  
  `samples_mo.txt` を WAV に変換する簡易スクリプト
- `tests/*.vgm`  
  YM2413 の各種テストパタン VGM
- `tests/*.vgm.csv`  
  `vgm_to_ym2413_csv.py` で VGM から生成した CSV

---

## YM2413 VGM → CSV (`tools/vgm_to_ym2413_csv.py`)

テストで使用するすべての CSV は、Python 版の `vgm_to_ym2413_csv.py` で生成します。

基本的な使い方:

```bash
python3 tools/vgm_to_ym2413_csv.py path/to/file.vgm
```

これにより、`path/to/file.vgm.csv` が生成されます。フォーマットは:

```text
delay,reg,data
0,01,0E
0,00,20
983,01,10
0,00,00
...
```

各カラムの意味:

- **delay**
  - 符号なし整数
  - VGM のサンプルカウンタ (`timestamp.current_sample`) の差分
  - 単位は「44.1kHz の PCM サンプル数」
  - テストベンチでは「次のレジスタアクセスまでの wait-before」として扱う
- **reg**
  - `"01"` → アドレスフェーズ (A0 = 0)
  - `"00"` → データフェーズ (A0 = 1)
- **data**
  - `"0E"` や `"0x20"` のような 16 進文字列

このリポジトリでは、例えば次のようにしてテスト用 CSV をまとめて再生成しています。

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

## CSV → Verilog インクルード (`tools/vgm_csv_to_vh.py`)

`vgm_csv_to_vh.py` は、上記 CSV を IKAOPLL 用の `.vh` に変換します。

使い方:

```bash
python3 tools/vgm_csv_to_vh.py tests/ym2413_scale_chromatic.vgm.csv \
  tests/ym2413_scale_chromatic.vh
```

生成される `.vh` の例:

```verilog
// Auto-generated from ym2413_scale_chromatic.vgm.csv
// Each # delay is a VGM *delta* (per-row delay) converted to 10ps ticks.

#2267532  IKAOPLL_write(1'b0, 8'h0E, phiMref, CS_n, WR_n, A0, DIN);
#0        IKAOPLL_write(1'b1, 8'h20, phiMref, CS_n, WR_n, A0, DIN);
#222218136 IKAOPLL_write(1'b0, 8'h10, phiMref, CS_n, WR_n, A0, DIN);
#0         IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
...
```

重要なポイント:

- `IKAOPLL_vgm_tb.sv` と同じく `timescale 10ps/10ps` を前提としています。
- EMUCLK 周波数は 3.579545 MHz。
- 各行の `#<ticks>` は **その行の delay（差分）** を 10ps tick に変換した値です。

  ```text
  ticks = delay * TICKS_PER_SAMPLE
  ```

- Verilog の `#` は「相対待ち」なので、CSV の per-row delay をそのまま `#` に使うことで、VGM の時間軸に忠実なレジスタアクセス間隔を再現します（バス書き込みに必要な数 µs は誤差として許容）。

---

## VGM テストベンチの実行

1. 必要なら VGM から CSV を生成:

   ```bash
   python3 tools/vgm_to_ym2413_csv.py tests/your_vgm.vgm
   ```

2. CSV から `.vh` を生成:

   ```bash
   python3 tools/vgm_csv_to_vh.py tests/your_vgm.vgm.csv tests/your_vgm.vh
   ```

3. テストベンチ側で該当 `.vh` を include:

   ```systemverilog
   `include "tests/your_vgm.vh"
   ```

4. iverilog 等でビルド・実行:

   ```bash
   iverilog -g2012 -o ikaopll_vgm_tb.vvp \
     src/IKAOPLL.v src/IKAOPLL_modules/IKAOPLL_*.v IKAOPLL_vgm_tb.sv

   vvp ikaopll_vgm_tb.vvp
   ```

テストベンチは:

- リセットをかけてから
- `.vh` の `IKAOPLL_write(...)` シーケンスを IKAOPLL に与え
- MO 側 DAC 出力 (`IMP_FLUC_SIGNED_MO`) を `samples_mo.txt` に書き出します。

---

## `samples_mo.txt` から WAV への変換

シミュレーション完了後、以下で WAV を生成できます。

```bash
python3 tools/txt_to_wav.py samples_mo.txt out.wav
```

これにより、シミュレーション結果のオーディオを実際に再生して確認できます。

---