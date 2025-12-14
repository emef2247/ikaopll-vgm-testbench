`timescale 10ps/10ps

module IKAOPLL_vgm_tb;

    // ------------------------------------------------------------
    // VCD
    // ------------------------------------------------------------
    initial begin
        $dumpfile("ikaopll_vgm_tb.vcd");
        $dumpvars(0, IKAOPLL_vgm_tb);
    end

    // ------------------------------------------------------------
    // Clock (~3.579545 MHz)
    // ------------------------------------------------------------
    reg EMUCLK = 1'b0;
    always #13968 EMUCLK = ~EMUCLK;

    reg [1:0] clkdiv  = 2'd0;
    reg       phiMref = 1'b0;

    always @(posedge EMUCLK) begin
        if (clkdiv == 2'd3) begin
            clkdiv  <= 2'd0;
            phiMref <= 1'b1;
        end else begin
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
        $display("[TB] Reset deasserted at %0t", $time);
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

    // ========================================================================
    //  phiM カウンタ（Wait 管理用）
    // ========================================================================
    integer phiM_cnt = 0;

    always @(posedge EMUCLK or negedge IC_n) begin
        if (!IC_n)
            phiM_cnt <= 0;
        else if (phiMref)
            phiM_cnt <= phiM_cnt + 1;
    end

    // 前回アクセス種別: 0=NONE, 1=ADDR, 2=DATA
    integer last_op_kind = 0;
    integer last_op_phiM = 0;

    localparam integer LAST_NONE = 0;
    localparam integer LAST_ADDR = 1;
    localparam integer LAST_DATA = 2;

    // 最低ウェイト
    localparam integer MIN_WAIT_ADDR = 12;
    localparam integer MIN_WAIT_DATA = 84;

    task automatic wait_phiM_cycles(input integer n);
        integer i;
        begin
            for (i = 0; i < n; i = i + 1)
                @(posedge phiMref);
        end
    endtask

    // ------------------------------------------------------------
    // Bus write task (Wait 強制版)
    // ------------------------------------------------------------
    task IKAOPLL_write;
        input        i_TARGET_ADDR;  // 0 = address, 1 = data
        input  [7:0] i_WRITE_DATA;
        input        i_CLK;          // 未使用
        inout        o_CS_n;         // ダミー
        inout        o_WR_n;
        inout        o_A0;
        inout  [7:0] o_DATA;
    begin
        integer need_wait;
        integer now_phiM;

        now_phiM = phiM_cnt;

        case (last_op_kind)
            LAST_ADDR: need_wait = MIN_WAIT_ADDR;
            LAST_DATA: need_wait = MIN_WAIT_DATA;
            default:   need_wait = 0;
        endcase

        if (need_wait > 0) begin
            integer diff;
            diff = now_phiM - last_op_phiM;
            if (diff < need_wait) begin
                integer remain;
                remain = need_wait - diff;
                $display("[TB] enforcing wait: last_op=%0d, diff=%0d, need=%0d -> wait %0d phiM cycles at %0t",
                         last_op_kind, diff, need_wait, remain, $time);
                wait_phiM_cycles(remain);
                now_phiM = phiM_cnt;
            end
        end

        $display("[TB] WRITE %s A0=%0d DATA=%02h at %0t (phiM_cnt=%0d)",
                 (i_TARGET_ADDR == 1'b0) ? "ADDR" : "DATA",
                 i_TARGET_ADDR, i_WRITE_DATA, $time, phiM_cnt);

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

        if (i_TARGET_ADDR == 1'b0)
            last_op_kind = LAST_ADDR;
        else
            last_op_kind = LAST_DATA;
        last_op_phiM = phiM_cnt;
    end
    endtask

    // ========================================================================
    //  ログ機構
    // ========================================================================
    integer fh_mo;
    integer fh_dur;
    integer fh_acc;

    integer cyc_cnt;
    integer dur_idx;

    longint dur_start_ps;
    longint dur_end_ps;
    reg     dur_inited;
    reg     ACC_STRB_q;

    initial begin
        fh_mo = $fopen("samples_mo.txt", "w");
        if (fh_mo == 0) begin
            $display("[TB] ERROR: cannot open samples_mo.txt");
            $finish;
        end
        fh_dur = $fopen("durations.txt", "w");
        if (fh_dur == 0) begin
            $display("[TB] ERROR: cannot open durations.txt");
            $finish;
        end
        fh_acc = $fopen("samples_acc.txt", "w");
        if (fh_acc == 0) begin
            $display("[TB] ERROR: cannot open samples_acc.txt");
            $finish;
        end

        cyc_cnt      = 0;
        dur_idx      = 0;
        dur_start_ps = 0;
        dur_end_ps   = 0;
        dur_inited   = 0;
        ACC_STRB_q   = 1'b0;

        $display("[TB] Logging initialized.");
    end

    // EMUCLK カウンタ
    always @(posedge EMUCLK or negedge IC_n) begin
        if (!IC_n)
            cyc_cnt <= 0;
        else
            cyc_cnt <= cyc_cnt + 1;
    end

    // Duration ログ
    always @(posedge EMUCLK or negedge IC_n) begin
        if (!IC_n) begin
            ACC_STRB_q   <= 1'b0;
            dur_idx      <= 0;
            dur_start_ps <= 0;
            dur_end_ps   <= 0;
            dur_inited   <= 0;
        end else begin
            ACC_STRB_q <= ACC_STRB;

            if (!ACC_STRB_q && ACC_STRB) begin
                longint now_ps;
                now_ps = cyc_cnt * 10;

                if (dur_inited) begin
                    dur_end_ps = now_ps;
                    $fwrite(fh_dur, "%0d %0d %0d\n",
                            dur_idx, dur_start_ps, dur_end_ps);
                    dur_idx <= dur_idx + 1;
                end

                dur_start_ps = now_ps;
                dur_inited   = 1'b1;
            end
        end
    end

    // MO ログ
    always @(posedge EMUCLK) begin
        if (DAC_EN_MO) begin
            longint time_ps;
            time_ps = cyc_cnt * 10;
            $fwrite(fh_mo, "%0d %0d %0d\n",
                    dur_idx,
                    $signed(IMP_FLUC_MO),
                    time_ps);
        end
    end

    // ACC ログ（値 + 時刻[ps]）
    always @(posedge EMUCLK) begin
        if (ACC_STRB) begin
            longint time_ps;
            time_ps = cyc_cnt * 10;
            $fwrite(fh_acc, "%0d %0d\n",
                    $signed(ACC_SIGNED),
                    time_ps);
        end
    end

    // ------------------------------------------------------------
    // Stimulus
    // ------------------------------------------------------------
    initial begin
        @(posedge IC_n);
        repeat (100) @(posedge EMUCLK);

        $display("[TB] Starting VGM pattern from tests/ym2413_scale_chromatic.vh at %0t", $time);

        `include "tests/ym2413_scale_chromatic.vh"

        $display("[TB] VGM pattern completed, waiting tail at %0t", $time);
        #10_000_000;

        $display("[TB] Finishing simulation at %0t", $time);
        $fclose(fh_mo);
        $fclose(fh_dur);
        $fclose(fh_acc);
        $finish;
    end

endmodule