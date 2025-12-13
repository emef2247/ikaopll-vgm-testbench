`timescale 10ps/10ps

// IKAOPLL_vgm_tb.sv
//  - IKAOPLL_tb_simple.sv と同じクロック / リセット / バスタイミング
//  - tools/vgm_csv_to_vh.py が生成した tests/ym2413_scale_chromatic.vh
//    を include して、VGM 由来のパターンを流す
//  - MO 側 DAC 出力 IMP_FLUC_MO を samples_mo.txt に記録

module IKAOPLL_vgm_tb;

    // ------------------------------------------------------------
    // VCD
    // ------------------------------------------------------------
    initial begin
        $dumpfile("ikaopll_vgm_tb.vcd");
        $dumpvars(0, IKAOPLL_vgm_tb);
    end

    // ------------------------------------------------------------
    // Clock (~3.579545 MHz, original tb と同じ)
    // ------------------------------------------------------------
    reg EMUCLK = 1'b0;
    always #13968 EMUCLK = ~EMUCLK;   // half-period 13968 * 10ps

    reg [1:0] clkdiv  = 2'd0;
    reg       phiMref = 1'b0;

    always @(posedge EMUCLK) begin
        if (clkdiv == 2'd3) begin
            clkdiv  <= 2'd0;
            phiMref <= 1'b1;
        end
        else begin
            clkdiv <= clkdiv + 2'd1;
            if (clkdiv == 2'd1)
                phiMref <= 1'b0;
        end
    end

    wire phiM_PCEN_n = 1'b0;

    // ------------------------------------------------------------
    // Reset
    // ------------------------------------------------------------
    reg IC_n = 1'b0;
    initial begin
        IC_n = 1'b0;
        repeat (64) @(posedge EMUCLK);
        IC_n = 1'b1;
    end

    // ------------------------------------------------------------
    // Bus / I/O
    // ------------------------------------------------------------
    reg        CS_n = 1'b1;
    reg        WR_n = 1'b1;
    reg        A0   = 1'b0;
    reg [7:0]  DIN  = 8'h00;

    wire [1:0] DOUT;
    wire       D_OE;

    wire       DAC_EN_MO;
    wire       DAC_EN_RO;
    wire       IMP_NOFLUC_SIGN;
    wire [7:0] IMP_NOFLUC_MAG;
    wire signed [9:0] IMP_FLUC_MO;
    wire signed [9:0] IMP_FLUC_RO;
    wire       ACC_STRB;
    wire signed [15:0] ACC_SIGNED;

    // ------------------------------------------------------------
    // DUT
    // ------------------------------------------------------------
    IKAOPLL #(
        .FULLY_SYNCHRONOUS        (1),
        .FAST_RESET               (1),
        .ALTPATCH_CONFIG_MODE     (0),
        .USE_PIPELINED_MULTIPLIER (0)
    ) dut (
        .i_XIN_EMUCLK             (EMUCLK),
        .o_XOUT                   ( /* unused */ ),

        .i_phiM_PCEN_n            (phiM_PCEN_n),

        .i_IC_n                   (IC_n),

        .i_ALTPATCH_EN            (1'b0),

        .i_CS_n                   (CS_n),
        .i_WR_n                   (WR_n),
        .i_A0                     (A0),

        .i_D                      (DIN),
        .o_D                      (DOUT),
        .o_D_OE                   (D_OE),

        .o_DAC_EN_MO              (DAC_EN_MO),
        .o_DAC_EN_RO              (DAC_EN_RO),
        .o_IMP_NOFLUC_SIGN        (IMP_NOFLUC_SIGN),
        .o_IMP_NOFLUC_MAG         (IMP_NOFLUC_MAG),
        .o_IMP_FLUC_SIGNED_MO     (IMP_FLUC_MO),
        .o_IMP_FLUC_SIGNED_RO     (IMP_FLUC_RO),

        .i_ACC_SIGNED_MOVOL       (5'sd2),
        .i_ACC_SIGNED_ROVOL       (5'sd3),
        .o_ACC_SIGNED_STRB        (ACC_STRB),
        .o_ACC_SIGNED             (ACC_SIGNED)
    );

    // ------------------------------------------------------------
    // Bus write task (7 引数版, .vh と一致)
    //   ただし実際には TB 内の CS_n/WR_n/A0/DIN を直接操作する。
    // ------------------------------------------------------------
    task IKAOPLL_write;
        input        i_TARGET_ADDR;  // 0 = address, 1 = data
        input  [7:0] i_WRITE_DATA;
        input        i_CLK;          // .vh からは phiMref が渡されるが未使用
        inout        o_CS_n;         // ダミー（接続はするが中では使わない）
        inout        o_WR_n;
        inout        o_A0;
        inout  [7:0] o_DATA;
    begin
        // デバッグ出力（必要なければ消してOK）
        $display("[TB] IKAOPLL_write call: A0=%0d DATA=%02h time=%0t",
                 i_TARGET_ADDR, i_WRITE_DATA, $time);

        // ここからは simple 版と同じく、モジュール内の CS_n/WR_n/A0/DIN を直に叩く
        @(posedge phiMref) A0   = i_TARGET_ADDR;
        @(negedge phiMref) CS_n = 1'b0;
        @(posedge phiMref) DIN  = i_WRITE_DATA;
        @(negedge phiMref) WR_n = 1'b0;
        @(posedge phiMref);
        @(negedge phiMref) begin
            WR_n = 1'b1;
            CS_n = 1'b1;
        end
        @(posedge phiMref) DIN  = 8'h00;
    end
    endtask
    // ------------------------------------------------------------
    // DAC logging (MO, IMP_FLUC_MO)
    // ------------------------------------------------------------
    integer fh_mo;
    initial begin
        fh_mo = $fopen("samples_mo.txt", "w");
        if (fh_mo == 0) begin
            $display("[TB] ERROR: cannot open samples_mo.txt");
            $finish;
        end
    end

    always @(posedge EMUCLK) begin
        if (DAC_EN_MO) begin
            $fwrite(fh_mo, "%0d\n", $signed(IMP_FLUC_MO));
        end
    end

    // ------------------------------------------------------------
    // Stimulus: VGM pattern include
    // ------------------------------------------------------------
    initial begin
        @(posedge IC_n);
        repeat (100) @(posedge EMUCLK);

        $display("[TB] Starting VGM pattern from tests/ym2413_scale_chromatic.vh");

        // ここで .vh を展開（各行が IKAOPLL_write(...) を呼ぶ）
        `include "tests/ym2413_scale_chromatic.vh"

        // パターン終了後の余韻
        #10_000_000;

        $display("[TB] VGM pattern completed, finishing.");
        $fclose(fh_mo);
        $finish;
    end

    // ------------------------------------------------------------
    // Global timeout
    // ------------------------------------------------------------
    //initial begin
    //    #200_000_000_000; // 2 s
    //    $display("[TB] Global timeout, finishing.");
    //    $fclose(fh_mo);
    //    $finish;
    //end

endmodule