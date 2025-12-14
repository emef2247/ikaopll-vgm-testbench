# IKAOPLL

IKAOPLL は、Verilog で書かれた「周期精度あり・完全同期型」の YM2413 (OPLL) コアです。

このリポジトリには、以下のようなテストベンチ環境とツールも含まれています。

- YM2413 向け VGM ファイルをシンプルな CSV 形式に変換する
- その CSV から、IKAOPLL バスをドライブする Verilog インクルード (`.vh`) を生成する
- シミュレーションを実行して DAC 関連の出力をテキストでダンプする
- それらのテキストを WAV に変換して試聴・解析する

英語版 README は [README.md](README.md) を参照してください。

---

## リポジトリ構成

- `src/IKAOPLL.v`, `src/IKAOPLL_modules/…`  
  IKAOPLL 本体およびサブモジュール
- `IKAOPLL_vgm_tb.sv`  
  VGM 由来のパターンを IKAOPLL に流し込み、DAC 関連の出力をダンプするテストベンチ
- `tools/vgm_to_ym2413_csv.py`  
  YM2413 コマンド専用の **VGM→CSV 変換スクリプト**
- `tools/vgm_csv_to_vh.py`  
  CSV→Verilog インクルード変換 – テストベンチから呼ばれる `IKAOPLL_write(...)` を生成
- `tools/txt_to_wav.py`  
  旧来の簡易テキスト→WAV 変換（`samples_mo.txt` 用）
- **波形解析用ヘルパ**
  - `tools/avg_mo_by_duration.py` – `IMP_FLUC_MO` を Duration 単位で平均  
  - `tools/avg_mo_to_wav.py` – 平均列を WAV に変換（簡易移動平均フィルタ付き）  
  - `tools/acc_to_wav.py` – `ACC_SIGNED` サンプル列を WAV に変換  
  - `tools/analyze_mo_range.py` – `samples_mo.txt` から `IMP_FLUC_MO` の最小値/最大値を計算  
  - `tools/analyze_duration.py` – `durations.txt` の簡易統計
- `tests/*.vgm`  
  YM2413 用の VGM テストパターン
- `tests/*.vgm.csv`  
  `vgm_to_ym2413_csv.py` で生成された CSV

---

## YM2413 VGM → CSV (`tools/vgm_to_ym2413_csv.py`)

テスト用 CSV（および自作の VGM 用 CSV）は、次のスクリプトで生成します。

```bash
python3 tools/vgm_to_ym2413_csv.py path/to/file.vgm
```

`path/to/file.vgm.csv` が生成され、内容は以下の形式です。

```text
delay,reg,data
0,01,0E
0,00,20
983,01,10
0,00,00
...
```

各列の意味:

- **delay**
  - 符号なし整数
  - VGM のサンプルカウンタ (`timestamp.current_sample`) の差分
  - 単位は 44.1 kHz PCM サンプル（VGM 標準）
  - テストベンチでは **「書き込み前の Wait」** として扱う
- **reg**
  - `"01"` → アドレスフェーズ (A0 = 0)
  - `"00"` → データフェーズ (A0 = 1)
- **data**
  - `"0E"` や `"20"` などの 16 進文字列

---

## CSV → Verilog インクルード (`tools/vgm_csv_to_vh.py`)

`vgm_csv_to_vh.py` は、CSV からテストベンチで `include` される `.vh` を生成します。

使い方:

```bash
python3 tools/vgm_csv_to_vh.py tests/ym2413_scale_chromatic.vgm.csv \
  tests/ym2413_scale_chromatic.vh
```

生成されるファイルの例:

```verilog
// Auto-generated from ym2413_scale_chromatic.vgm.csv
// Each # delay is a VGM *delta* (per-row delay) converted to 10ps ticks.

#2267532 IKAOPLL_write(1'b0, 8'h0E, phiMref, CS_n, WR_n, A0, DIN);
#0       IKAOPLL_write(1'b1, 8'h20, phiMref, CS_n, WR_n, A0, DIN);
#222218136 IKAOPLL_write(1'b0, 8'h10, phiMref, CS_n, WR_n, A0, DIN);
#0         IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
...
```

注意点:

- `timescale 10ps/10ps` を前提としています（`IKAOPLL_vgm_tb.sv` と一致させる必要があります）。
- EMUCLK は 3.579545 MHz を想定しています。
- 各 `#<ticks>` は **行ごとの delay（delta）** で、  
  `ticks = delay * TICKS_PER_SAMPLE` で計算されます。
- Verilog の `#` は相対ディレイなので、CSV の delta をそのまま使うのが正しいです。

---

## VGM テストベンチの実行

1. VGM から CSV を生成（自作 VGM を使う場合）:

   ```bash
   python3 tools/vgm_to_ym2413_csv.py tests/your_vgm.vgm
   ```

2. CSV から `.vh` を生成:

   ```bash
   python3 tools/vgm_csv_to_vh.py tests/your_vgm.vgm.csv tests/your_vgm.vh
   ```

3. テストベンチが正しい `.vh` を `include` していることを確認:

   ```systemverilog
   `include "tests/your_vgm.vh"
   ```

4. テストベンチをビルド＆実行（Icarus Verilog の例）:

   ```bash
   iverilog -g2012 -o ikaopll_vgm_tb.vvp \
     src/IKAOPLL.v src/IKAOPLL_modules/IKAOPLL_*.v IKAOPLL_vgm_tb.sv

   vvp ikaopll_vgm_tb.vvp
   ```

テストベンチの挙動:

- リセットをかける
- VGM 由来のバスパターンを IKAOPLL に印加
- OPLL 仕様に従い、**アドレス書き込み後 12 サイクル、データ書き込み後 84 サイクル** の Wait を
  テストベンチ側で強制する（VGM の Wait 値が 0 などでも安全）
- 以下のテキストファイルを出力:
  - `samples_mo.txt` – `IMP_FLUC_SIGNED_MO`（MO 側 DAC 入力相当）
  - `durations.txt` – `ACC_STRB` に基づく Duration ごとの開始/終了時刻
  - `samples_acc.txt` – `ACC_SIGNED`（オペレータ合成後の加算結果）

---

## シミュレーションログから WAV を作る

OPLL の動作確認やラフな試聴のために、テキストログを WAV に変換するツールを用意しています。

### 1. Mo ベースの WAV（簡易・安定版）

`IMP_FLUC_MO` を Duration ごとに平均したものを、比較的「安定した信号」とみなして WAV にします。

1. **Duration ごとに Mo を平均**

   ```bash
   python3 tools/avg_mo_by_duration.py samples_mo.txt
   ```

   - 出力: `avg_mo_by_duration.txt`
   - 内容: 1 行 1 サンプル（Duration インデックスごとの平均値）

2. **平均列を WAV に変換（移動平均付き）**

   ```bash
   # 48kHz, 窓長 15 の移動平均フィルタ
   python3 tools/avg_mo_to_wav.py avg_mo_by_duration.txt mo_avg_ma15_48k.wav 48000 15

   # 44.1kHz で書き出す場合
   python3 tools/avg_mo_to_wav.py avg_mo_by_duration.txt mo_avg_ma15_44k1.wav 44100 15
   ```

   - 第 4 引数: サンプリングレート (Hz)
   - 第 5 引数: 移動平均の窓長（奇数が推奨。例: 5, 9, 15 …）

   このパスは、

   - 音の長さ・テンポ
   - 複数ノートの並び
   - 大まかな音量変化

   を確認するのに向いています（音色自体はかなり簡素です）。

### 2. ACC ベースの WAV（実験的）

テストベンチで ACC ログを有効にしている場合、`samples_acc.txt` に `ACC_SIGNED` が 1 サンプル／`ACC_STRB` で記録されます。これをそのまま WAV に変換できます。

```bash
# 48kHz
python3 tools/acc_to_wav.py samples_acc.txt acc_48k.wav

# 44.1kHz
python3 tools/acc_to_wav.py samples_acc.txt acc_44k1.wav 44100
```

こちらは OPLL 内部での加算結果に近い信号ですが、

- `ACC_STRB` の出現頻度
- どのクロックでサンプリングするか

などの解釈に依存するため、音としてはノイジー／スカスカになることがあります。  
主に解析や実験用途を想定しています。

### 3. 旧来の `samples_mo.txt` → WAV

より単純に `samples_mo.txt` を固定レートの時系列として扱うヘルパも残しています。

```bash
python3 tools/txt_to_wav.py samples_mo.txt out.wav
```

現在は、Duration 平均を経由するパス（`avg_mo_by_duration.py` → `avg_mo_to_wav.py`）の方が実用的です。

---

## 解析用の小さなツール

- **`tools/analyze_mo_range.py`** – `IMP_FLUC_MO` のレンジ確認

  ```bash
  python3 tools/analyze_mo_range.py samples_mo.txt
  ```

  出力例:

  ```text
  # file   : samples_mo.txt
  # count  : 3224715
  min MO   : 1
  max MO   : 34
  ```

- **`tools/analyze_duration.py`** – Duration 情報の統計

  ```bash
  python3 tools/analyze_duration.py durations.txt
  ```

  Duration ごとの長さ（ps）の最小・最大・平均・標準偏差、および  
  「1 Duration を 1 サンプルとみなしたときの実効サンプリングレート」などを表示します。

これらはテストベンチ／ツールチェインを調整するときの目安として使えます。

## シミュレーションログから WAV を作る

OPLL の動作確認やラフな試聴のために、テキストログを WAV に変換するツールを用意しています。

### 1. ワンショットで参照 WAV を生成する

`IKAOPLL_vgm_tb.sv` を実行すると、以下のテキストが生成されます。

- `samples_mo.txt` – `IMP_FLUC_SIGNED_MO`（MO 側）
- `samples_acc.txt` – `ACC_SIGNED`（オペレータ合成後）

これらから **Mo ベース**と **ACC ベース**の 2 種類の参照 WAV を一度に作るラッパスクリプトが `tools/make_ref_wav.py` です。

```bash
python3 tools/make_ref_wav.py
```

カレントディレクトリに

- `mo_ref_44k1.wav`
- `acc_ref_44k1.wav`

が生成されます（いずれも 1ch, 16bit）。

#### Mo ベース参照 WAV (`mo_ref_44k1.wav`)

内部では、従来の

- `avg_mo_by_duration.py`
- `avg_mo_to_wav.py`

と同じ処理を行っています。

1. `samples_mo.txt`（形式: `dur_idx value time_ps`）から  
   duration インデックスごとに `value` を平均
2. 平均列に対して簡易な移動平均フィルタ（窓長 15）
3. 正規化して Fs=44.1kHz で WAV 出力

特徴:

- 音色はかなり簡素ですが、
  - 全体の長さ
  - テンポ
  - ノートの出入り
- を確認するには十分です。

#### ACC ベース参照 WAV (`acc_ref_44k1.wav`)

内部では、従来の `acc_decimate_to_wav.py` 相当の処理を行っています。  
`ACC_SIGNED` を「内部サンプリングレート Fs_int ≒ 1.6MHz の等間隔サンプル」とみなし、  
ローパス＋間引きで 44kHz 付近に落としています。

処理の概要:

1. `samples_acc.txt` を読み込み
   - 行形式は `value` または `value time_ps`（先頭列だけ使用）
   - 先頭に `x 0` などがある場合は警告を出しつつスキップ
2. 内部サンプリングレートを **Fs_int = 1_600_000 Hz** と仮定
3. 目標出力レート **Fs_out_target = 44_100 Hz** から
   デシメーション係数 `decim ≈ Fs_int / Fs_out_target` を計算  
   → 現状のテストでは `decim = 36`、有効出力レートは約 **44.44 kHz**
4. 簡易ローパス（移動平均: 窓長 = `decim * 3`）を適用
5. `decim` サンプルごとに 1 サンプルを取り出して間引き
6. 正規化して WAV 出力

この WAV は

- Mo 版よりノイジーですが、
- 長さ・音量・ノートの鳴るタイミングは VGM の印象にかなり近く、
- 波形としては ACC_SIGNED に近い「FM らしい形」を保ったまま  
  44kHz 近傍に落としたもの

になっています。

#### Verilator / C 実装との対応

将来、Verilator + C/C++ ドライバ側で同じ処理を実装する場合は、次の点を合わせておくと比較が容易です。

- 内部レート仮定: `Fs_int = 1_600_000 Hz`
- デシメーション係数: `decim = 36`
- 実効出力レート: `Fs_out ≈ 44_444.44 Hz`
- 簡易 LPF:
  - 移動平均窓長 ≒ `decim * 3`
- 正規化:
  - `max(|x|)` を ±`0.9 * 32767` に合わせて 16bit 変換

この README に書かれている仕様と `tools/make_ref_wav.py` の実装が「期待値」となり、  
C 側の WAV 出力とバイト単位（または ±1 LSB 程度）で比較できるようになります。

### 2. 個別ツールを直接使う場合

ワンショットスクリプトではなく、個別のツールを直接触りたい場合は、従来どおり:

- Mo 系
  - `tools/avg_mo_by_duration.py`
  - `tools/avg_mo_to_wav.py`
- ACC 系
  - `tools/acc_to_wav.py`（高 Fs=1MHz などで波形・スペクトル確認用）
  - `tools/acc_decimate_to_wav.py`（内部 Fs 仮定 + ローパス + デシメーション）

を使うこともできます。