# IKAOPLL 用 新規 testbench 設計メモ

目的:  
- 既存の `IKAOPLL` RTL（`src/IKAOPLL.v` 以下）を**変更せず**に使う。  
- SystemVerilog/iverilog の testbench で  
  - まず「既存 `IKAOPLL_tb.sv` のレジスタ書き込みパターン」で音が出ることを確認する。  
  - 次に `tests/*.vgm.csv`（例: `ym2413_scale_chromatic.vgm.csv`）を読み込み、VGM に従って OPLL を駆動し、`o_ACC_SIGNED` をロギングできるようにする。  
- 最終的には、このモデルを Verilator に持ち込み、VGM プレーヤに組み込む。

以下では、**新規 tb の構成とタイミング設計**をまとめる。

---

## 1. DUT とクロック／リセットの基本仕様

### 1.1 DUT: `IKAOPLL`

ポートのポイント:

- `i_XIN_EMUCLK`  
  - OPLL のマスタークロック `phiM` 相当。  
  - 今回は**実機に近い ≒ 3.579545 MHz** で駆動する。
- `i_phiM_PCEN_n`  
  - 「phiM の正エッジ用クロックイネーブル（負論理）」。
  - 内部タイミングジェネレータ (`IKAOPLL_timinggen`) では  
    `always @(posedge i_EMUCLK) if(!i_phiM_PCEN_n) ...` の形で使用。
  - 今回の用途（単独動作で常時駆動）では **常に enable (0 固定)** とする。
- `i_IC_n`  
  - 同期リセット。  
  - README より:
    - `FAST_RESET=0` なら、phiM 72 サイクル以上の Low が必要。
    - `FAST_RESET=1` なら 18 サイクル以上。
- `i_ACC_SIGNED_MOVOL`, `i_ACC_SIGNED_ROVOL`  
  - 5bit のボリュームスケール入力。  
  - これが 0 のままだと `o_ACC_SIGNED` は常に 0 になり得るので、**必ず非ゼロ**を与える。

出力:

- `o_ACC_SIGNED_STRB`  
  - 積算出力 `o_ACC_SIGNED` が更新されるタイミングのストローブ。
- `o_ACC_SIGNED[15:0]`  
  - 16bit の「最終デジタル出力」。  
  - WAV などに変換する場合は、**この値をサンプルとして使う**。

---

## 2. 新規 testbench のトップレベル構成

### 2.1 ファイル名と役割

- 新 tb ファイル（仮名）: `src/IKAOPLL_vgm_tb.sv`
- 役割:
  1. クロック生成（実 OPLL クロック ≒3.58MHz）
  2. リセットシーケンス生成
  3. DUT インスタンス化（`IKAOPLL`）
  4. `IKAOPLL_tb.sv` の固定レジスタ書き込みパターンの実行（フェーズ1）
  5. CSV (`ym2413_scale_chromatic.vgm.csv` など) を読み込み、VGM delay に従ってバス書き込み（フェーズ2）
  6. `o_ACC_SIGNED_STRB` に合わせて `o_ACC_SIGNED` をログ出力

### 2.2 クロック生成

- `timescale 10ps/10ps`
- 実 OPLL クロックに近い周期で `emuclk` を生成:

  - OPLL 実クロック: `f_M ≈ 3.579545 MHz`
  - 周期 `T ≈ 1 / f_M ≈ 279.365 ns`
  - `timescale 10ps` なので 1 tick = 10 ps
    - 半周期 ≈ 139.6825 ns → ≈ 13,968 ticks（丸め）
  - 実装:
    ```systemverilog
    reg emuclk = 1'b0;
    always #13968 emuclk = ~emuclk;   // 約 3.5796 MHz
    ```

- DUT への接続:
  ```systemverilog
  .i_XIN_EMUCLK (emuclk),
  ```

### 2.3 phiM イネーブル (`i_phiM_PCEN_n`)

- 第一版では**常に enable** とする:
  ```systemverilog
  wire phiM_PCEN_n = 1'b0;
  ...
  .i_phiM_PCEN_n (phiM_PCEN_n),
  ```
- これにより、phiM の全正エッジで内部タイミング（phi1 等）が進行する。

（将来的に「phiM を外部で間引く」必要が出たら、ここに分周ロジックを挿入する余地を残しておく。）

### 2.4 リセット (`i_IC_n`)

- パラメータ `FAST_RESET` を tb で明示:

  - 例えば:
    ```systemverilog
    localparam FAST_RESET = 1;   // 18 phiM cycles で十分
    ```
  - DUT インスタンスでは:
    ```systemverilog
    IKAOPLL #(
      .FULLY_SYNCHRONOUS        (1),
      .FAST_RESET               (FAST_RESET),
      .ALTPATCH_CONFIG_MODE     (0),
      .USE_PIPELINED_MULTIPLIER (0)
    ) dut ( ... );
    ```

- `i_IC_n` の駆動:
  ```systemverilog
  reg IC_n = 1'b0;
  initial begin
      // emuclk の立ち上がり 18〜数十サイクル程度 Low にしてから High にする
      repeat (64) @(posedge emuclk);  // 安全に多め
      IC_n = 1'b1;
  end
  ...
  .i_IC_n (IC_n),
  ```

### 2.5 ボリューム入力

- かならず非ゼロ値で固定:
  ```systemverilog
  .i_ACC_SIGNED_MOVOL (5'sd2),
  .i_ACC_SIGNED_ROVOL (5'sd3),
  ```

---

## 3. バス信号と書き込みタスク

### 3.1 バス信号

- tb 内部で以下を宣言:
  ```systemverilog
  reg        CS_n = 1'b1;
  reg        WR_n = 1'b1;
  reg        A0   = 1'b0;
  reg [7:0]  DIN  = 8'h00;
  ```

- DUT には:

  ```systemverilog
  .i_CS_n (CS_n),
  .i_WR_n (WR_n),
  .i_A0   (A0),
  .i_D    (DIN),
  ```

### 3.2 `IKAOPLL_tb.sv` の書き込みタスク

既存 tb からタスクをほぼそのまま利用:

```systemverilog
task automatic IKAOPLL_write (
    input               i_TARGET_ADDR,   // A0
    input       [7:0]   i_WRITE_DATA,
    ref logic           i_CLK,           // phiMref 相当
    ref logic           o_CS_n,
    ref logic           o_WR_n,
    ref logic           o_A0,
    ref logic   [7:0]   o_DATA
);
begin
    @(posedge i_CLK) o_A0 = i_TARGET_ADDR;
    @(negedge i_CLK) o_CS_n = 1'b0;
    @(posedge i_CLK) o_DATA = i_WRITE_DATA;
    @(negedge i_CLK) o_WR_n = 1'b0;
    @(posedge i_CLK);
    @(negedge i_CLK) begin
        o_WR_n = 1'b1;
        o_CS_n = 1'b1;
    end
    @(posedge i_CLK) o_DATA = 8'h00; // バス開放（0 でも ZZ でも可、後で調整）
end
endtask
```

### 3.3 `phiMref` 相当のクロック

- 既存 `IKAOPLL_tb.sv` 同様に、`emuclk` を 4 分周して書き込み用の参照クロック `phiMref` を生成する。

  ```systemverilog
  reg [1:0] clkdiv = 2'd0;
  reg       phiMref = 1'b0;

  always @(posedge emuclk) begin
      if (clkdiv == 2'd3) begin
          clkdiv  <= 2'd0;
          phiMref <= 1'b1;
      end else begin
          clkdiv  <= clkdiv + 2'd1;
          if (clkdiv == 2'd1) phiMref <= 1'b0;
      end
  end
  ```

- これは「既存 tb の書き込みタイミングとほぼ同じ」になるようにしたい、という意図。

---

## 4. フェーズ1: CSV なし・固定パターンで鳴らす

### 4.1 目的

- CSV 読み込みに進む前に、
  - クロック／リセット／バス書き込み／ボリューム入力が正しいこと
  - `o_ACC_SIGNED_STRB` に合わせて `o_ACC_SIGNED` が非ゼロで変化すること

を確認する。

### 4.2 シーケンス

- `initial` ブロックで以下の流れ:

  1. リセット解除（上で述べた `IC_n` シーケンス完了）まで待つ:
     ```systemverilog
     initial begin
         // リセット完了まで待つ
         @(posedge IC_n);
         // さらに少し待つ
         repeat (100) @(posedge emuclk);
         ...
     end
     ```

  2. 既存 `IKAOPLL_tb.sv` の最初のレジスタ設定をそのまま（あるいは必要な部分だけ）呼ぶ:

     ```systemverilog
     // 例: 既存 tb の #100 IKAOPLL_write(...) 群を、#delay をそのまま/または短縮した形で持ってくる
     #100 IKAOPLL_write(1'b0, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
     #100 IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
     ...
     ```

- ここでは**音が鳴くことだけが目的**なので、波形と `o_ACC_SIGNED` ログで確認できれば十分。

### 4.3 `o_ACC_SIGNED` のロギング

- シンプルに `o_ACC_SIGNED_STRB` をトリガにする:

  ```systemverilog
  integer fh;
  initial begin
      fh = $fopen("samples_phase1.txt", "w");
      if (fh == 0) begin
          $display("ERROR: cannot open samples_phase1.txt");
          $finish;
      end
  end

  always @(posedge emuclk) begin
      if (o_ACC_SIGNED_STRB) begin
          $fwrite(fh, "%0d\n", $signed(o_ACC_SIGNED));
      end
  end
  ```

- これで「STRB が立っているのに値が常に 0」という状態なら、  
  レジスタ設定 or ボリューム or さらに他の問題に絞り込める。

---

## 5. フェーズ2: CSV (`ym2413_scale_chromatic.vgm.csv` 等) 駆動

### 5.1 VGM delay → emuclk クロック数

- VGM delay の単位:
  - `1 step = 1 / 44100 s ≈ 22.6757 μs`
- emuclk 周波数:
  - `f_M ≈ 3.579545 MHz` → `T ≈ 279.365 ns`
- 1 step あたりの emuclk サイクル数は:
  \[
    EMU\_PER\_STEP ≈ \frac{3{,}579{,}545}{44{,}100} ≈ 81.2
  \]
- 整数に丸めて:
  ```systemverilog
  localparam int EMU_PER_STEP = 81;
  ```

### 5.2 CSV 読み込みと delay 処理

- `initial` ブロックで file I/O:

  1. ファイルオープン:
     ```systemverilog
     integer csv_fh;
     string  line;
     int     delay;
     string  reg_s, data_s;
     int     reg_bit;
     int     data_val;
     ```

  2. ヘッダ行 (`delay,reg,data`) を読み飛ばす:
     ```systemverilog
     csv_fh = $fopen("tests/ym2413_scale_chromatic.vgm.csv", "r");
     if (csv_fh == 0) begin
         $display("ERROR: cannot open CSV");
         $finish;
     end
     void'($fgets(line, csv_fh)); // header skip
     ```

  3. ループで 1 行ずつ処理:
     ```systemverilog
     while ($fgets(line, csv_fh)) begin
         // delay,reg,data を文字列として読み取る
         if ($sscanf(line, "%d,%s,%s", delay, reg_s, data_s) != 3) continue;

         // reg_s ("01"/"00") → 整数ビットへ
         if (reg_s == "01") reg_bit = 1;
         else               reg_bit = 0;

         // data_s ("0E" or "0x20" 等) を 8bit 整数に変換
         if (data_s.len() >= 2 && data_s.substr(0,2) == "0x")
             void'($sscanf(data_s.substr(2), "%x", data_val));
         else
             void'($sscanf(data_s, "%x", data_val));

         // delay * EMU_PER_STEP だけ emuclk を回す
         repeat (delay * EMU_PER_STEP) @(posedge emuclk);

         // 書き込み実行:
         //   reg_bit=1 → アドレスレジスタ (A0=0 or 1 は TB ルールに従う)
         //   reg_bit=0 → データレジスタ
         if (reg_bit == 1) begin
             // アドレス write
             IKAOPLL_write(1'b0, data_val[7:0], phiMref, CS_n, WR_n, A0, DIN);
         end else begin
             // データ write
             IKAOPLL_write(1'b1, data_val[7:0], phiMref, CS_n, WR_n, A0, DIN);
         end
     end
     ```

- ここでは「元 VGM ログ通り、delay を 1/44100 秒単位とみなし、そのぶん emuclk を 81 クロック回した後に書き込みを行う」モデルになる。

### 5.3 サンプルログ

- フェーズ1と同様、`o_ACC_SIGNED_STRB` で `o_ACC_SIGNED` を記録:
  ```systemverilog
  integer fh;
  initial begin
      fh = $fopen("samples_scale_chromatic.txt", "w");
      ...
  end

  always @(posedge emuclk) begin
      if (o_ACC_SIGNED_STRB)
          $fwrite(fh, "%0d\n", $signed(o_ACC_SIGNED));
  end
  ```

- このテキストを Python 等で WAV に変換すれば、  
  実際の `ym2413_scale_chromatic` の音が出ているかを確認できる。

---

## 6. フェーズ3（将来）: Verilator / プレーヤ統合

この tb の設計をそのまま C++ に写像すると:

- `emuclk` は Verilator 側で「クロック1サイクル = `eval()` 2回 (posedge/negedge)」のような形で実現。
- VGM プレーヤでは CSV ではなく、VGM コマンド列を直接読み、
  - delay N ごとに `N * EMU_PER_STEP` だけ emuclk を進めるループを回す。
- `o_ACC_SIGNED_STRB` が立っているときの `o_ACC_SIGNED` を、  
  プレーヤ内のオーディオバッファ（44100Hz想定）に書き込む。

このために、今回の tb では:

- delay→emuclk クロック変換
- `o_ACC_SIGNED_STRB` ベースのサンプリング

という「抽象モデル」を最初から採用している。

---

## 7. 次のアクション

1. この `.md` をベースに、新ファイル `IKAOPLL_vgm_tb.sv` の雛形を作成する。
2. まずはフェーズ1（CSV なし固定パターン＋`samples_phase1.txt` ログ）を実装し、  
   `o_ACC_SIGNED` が非ゼロで動くことを確認。
3. 次にフェーズ2として、`ym2413_scale_chromatic.vgm.csv` を読み込むロジックを追加・検証する。

必要があれば、各フェーズごとに別の tb ファイルに分けることもできるが、  
初期段階では 1 つの tb ファイルの中で `ifdef` や `parameter` で切り替える形でもよい。

