# ikaopll-vgm-testbench

Experimental YM2413 (OPLL) testbench using the IKAOPLL core and VGM/CSV playback.

このリポジトリは、元の [IKAOPLL](https://github.com/ika-musume/IKAOPLL) コア（Sehyeon Kim 氏, Raki）の上に構築した、**スタンドアロンのシミュレーション用プレイグラウンド**です。

主な目的は:

- YM2413 (OPLL) の動作を **VGM 由来のレジスタ書き込みトレース**で検証すること
- 将来、VGM プレーヤ／エミュレータに IKAOPLL コアを組み込むための足場を作ること

です。

> 注意: ここは **公式の IKAOPLL リポジトリではありません**。  
> IKAOPLL 本体およびドキュメントは Sehyeon Kim (Raki) 氏の著作物であり、BSD 2‑Clause License の下で本リポジトリに取り込まれています。

---

## 内容物

- `src/IKAOPLL.v`, `src/IKAOPLL_modules/…`  
  オリジナルの IKAOPLL YM2413 コア（コードは基本的に無改変）。

- `src/IKAOPLL_tb.sv`  
  IKAOPLL 元リポジトリが提供しているオリジナルのテストベンチ。

- `src/IKAOPLL_vgm_tb.sv`  
  本プロジェクト用に追加した SystemVerilog テストベンチ:
  - 実機 YM2413 に近い約 3.58 MHz の `EMUCLK` を生成
  - `FAST_RESET` の仕様に従ったリセットシーケンス
  - IKAOPLL のバスタイミングに合わせた書き込みタスク（iverilog 互換）
  - VCD (Value Change Dump) の自動生成による波形デバッグ
  - DAC 出力 (`o_DAC_EN_MO` / `o_IMP_FLUC_SIGNED_MO`) のコンソール出力
  - （今後予定）VGM→CSV 化したレジスタトレースを読み込んで駆動

- `tests/*.vgm.csv`  
  **openMSX 上で動作する MSX + MSGDRV** から取得した YM2413 レジスタ書き込みトレースを、  
  一度 VGM としてキャプチャしたのち、CSV に変換したものです。主な内容:

  - クロマチックスケール、ブロック境界などのスケール系パターン
  - リズムモードの ON/OFF テスト
  - パッチチェンジ・レガート・リトリガの挙動確認
  - 冗長な FNUM 書き込み、音量スイープなど

- `doc/tb_design_plan.md`  
  新しい VGM 指向テストベンチ (`IKAOPLL_vgm_tb.sv`) の設計メモ・方針。

- `docs/…`  
  YM2413 のデータシート／アプリケーションマニュアル／回路図／参考画像などの資料一式。

---

## 現在のステータス

現時点でできていること:

- **iverilog** 上で IKAOPLL コアをインスタンスして動作させることができる。
- 新しいテストベンチ `IKAOPLL_vgm_tb.sv` により:
  - 実 OPLL に近い `EMUCLK` の生成
  - リセットシーケンスの発行
  - バス書き込みタスクによるレジスタ設定
  - VCD 出力による波形デバッグ
  - `o_DAC_EN_MO` / `o_IMP_FLUC_SIGNED_MO` のコンソールログ

まで確認済みです。

今後の予定:

1. DAC 出力（例: `IMP_FLUC_MO`）をテキストファイルに記録するロガーの追加。
2. VGM→CSV のテストパターンをテストベンチから再生するロジックの実装:
   - `tests/ym2413_*.vgm.csv` の 1 行ごとに delay / reg / data を解釈
   - VGM の delay（1/44100 秒単位）を EMUCLK のクロック数に変換
   - 適切なタイミングでアドレス／データの書き込みタスクを発行
3. 記録したサンプル列から 44.1 kHz WAV を生成するための簡易スクリプト（例: Python）の用意。

---

## iverilog によるビルドと実行

リポジトリのルートで:

```bash
# ビルド（SystemVerilog 対応の iverilog が必要）
iverilog -g2012 -o ikaopll_vgm_tb.vvp \
  src/IKAOPLL.v \
  src/IKAOPLL_modules/IKAOPLL_*.v \
  src/IKAOPLL_vgm_tb.sv

# 実行
vvp ikaopll_vgm_tb.vvp
```

実行すると:

- `ikaopll_vgm_tb.vcd` が生成され、GTKWave などで波形が見られます。
- 標準出力には DAC のアクティビティが表示されます。例:

```text
VCD info: dumpfile ikaopll_vgm_tb.vcd opened for output.
[321264] DAC_EN_MO=1 IMP_FLUC_MO=1 (0x001)
…
```

波形を確認するには:

```bash
gtkwave ikaopll_vgm_tb.vcd &
```

を実行し、以下の信号を追加すると状況が追いやすいです。

- 上位信号:
  - `IC_n`, `EMUCLK`
  - `CS_n`, `WR_n`, `A0`, `DIN`
- DAC/出力:
  - `o_DAC_EN_MO`, `o_IMP_FLUC_SIGNED_MO`
- 内部レジスタ（必要に応じて）:
  - `dut.u_REG.fnum`
  - `dut.u_REG.block`
  - `dut.u_REG.kon`
  など

---

## ライセンスとクレジット

- IKAOPLL コア（`src/IKAOPLL.v`, `src/IKAOPLL_modules/…`）および元のドキュメントは:
  - © 2024 Sehyeon Kim (Raki)
  - **BSD 2‑Clause License** の下で配布されています（詳細は [LICENSE](LICENSE) を参照してください）。

- 本リポジトリで追加したファイル（テストベンチ、CSV テスト、設計メモなど）も、
  互換性とシンプルさのために **同じ BSD 2‑Clause License** の下で公開することを意図しています。

本プロジェクトを利用する際は、オリジナルの IKAOPLL 作者およびリポジトリへのクレジットもぜひ明示してください:

- [IKAOPLL on GitHub](https://github.com/ika-musume/IKAOPLL)

--- 