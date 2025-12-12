`timescale 10ps/10ps

// IKAOPLL_vgm_tb.sv
// New SystemVerilog testbench for IKAOPLL.
// Phase 1: use built‑in pattern (adapted from IKAOPLL_tb.sv) to confirm basic sound output.
// Phase 2: (to be added) drive IKAOPLL from VGM CSV (e.g. ym2413_scale_chromatic.vgm.csv).

module IKAOPLL_vgm_tb;

    // 波形デバッグ用 (VCD)
    initial begin
        $dumpfile("ikaopll_vgm_tb.vcd");
        $dumpvars(0, IKAOPLL_vgm_tb);
    end
	
    // ============================================================
    // 1. Clock generation (approx. real OPLL clock)
    // ============================================================

    // OPLL master clock ~3.579545 MHz
    // Period ≈ 279.365 ns → half period ≈ 139.6825 ns
    // With timescale 10ps, 1 tick = 10ps → half ≈ 13968 ticks.
    reg EMUCLK = 1'b0;
    always #13968 EMUCLK = ~EMUCLK;

    // phiM reference for bus timing (4‑div of EMUCLK, same style as IKAOPLL_tb.sv)
    reg  [1:0] clkdiv  = 2'd0;
    reg        phiMref = 1'b0;

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

    // phiM positive edge clock enable (negative logic)
    // For now keep always enabled (all phiM edges valid).
    wire phiM_PCEN_n = 1'b0;

    // ============================================================
    // 2. Reset
    // ============================================================

    // Use FAST_RESET=1 in DUT; need at least 18 phiM cycles asserted.
    // Here we keep reset low for 64 EMUCLK cycles for safety.
    reg IC_n = 1'b0;
    initial begin
        IC_n = 1'b0;
        repeat (64) @(posedge EMUCLK);
        IC_n = 1'b1;
    end

    // ============================================================
    // 3. Bus and I/O signals
    // ============================================================

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

    // ============================================================
    // 4. DUT instance (IKAOPLL core)
    // ============================================================

    localparam FAST_RESET = 1;

    IKAOPLL #(
        .FULLY_SYNCHRONOUS        (1),
        .FAST_RESET               (FAST_RESET),
        .ALTPATCH_CONFIG_MODE     (0),
        .USE_PIPELINED_MULTIPLIER (0)
    ) dut (
        .i_XIN_EMUCLK             (EMUCLK),
        .o_XOUT                   (/* unused */),

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

        // give non‑zero volumes so ACC_SIGNED is not muted
        .i_ACC_SIGNED_MOVOL       (5'sd2),
        .i_ACC_SIGNED_ROVOL       (5'sd3),
        .o_ACC_SIGNED_STRB        (ACC_STRB),
        .o_ACC_SIGNED             (ACC_SIGNED)
    );

    // ============================================================
    // 5. Bus write task (iverilog-compatible, no ref ports)
    // ============================================================

    task automatic IKAOPLL_write (
        input        i_TARGET_ADDR,
        input  [7:0] i_WRITE_DATA,
        input        i_CLK,
        inout        o_CS_n,
        inout        o_WR_n,
        inout        o_A0,
        inout  [7:0] o_DATA
    );
    begin
        @(posedge i_CLK) o_A0   = i_TARGET_ADDR;
        @(negedge i_CLK) o_CS_n = 1'b0;
        @(posedge i_CLK) o_DATA = i_WRITE_DATA;
        @(negedge i_CLK) o_WR_n = 1'b0;
        @(posedge i_CLK);
        @(negedge i_CLK) begin
            o_WR_n = 1'b1;
            o_CS_n = 1'b1;
        end
        @(posedge i_CLK) o_DATA = 8'h00;
    end
    endtask

    // ============================================================
    // 6. ACC_SIGNED debug: print to console when STRB rises
    // ============================================================

    // MO 側 DAC 出力をそのまま観測する
	always @(posedge EMUCLK) begin
		if (DAC_EN_MO) begin
			$display("[%0t] DAC_EN_MO=1 IMP_FLUC_MO=%0d (0x%03h)",
					 $time, $signed(IMP_FLUC_MO), IMP_FLUC_MO);
		end
	end
	
    // ============================================================
    // 7. Phase 1 stimulus:
    //    Reuse IKAOPLL_tb.sv register pattern to confirm output
    // ============================================================

    initial begin
        // wait until reset is released
        @(posedge IC_n);
        // small extra delay for safety
        repeat (100) @(posedge EMUCLK);

        // ---- BEGIN pattern copied/adapted from IKAOPLL_tb.sv ----
        // You can trim or adjust delays as needed; here we mostly keep them.

        #1500;

        #100 IKAOPLL_write(1'b0, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h01, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h02, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h00, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h03, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h18, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h04, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h7A, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h05, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h59, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h06, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h30, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h07, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h59, phiMref, CS_n, WR_n, A0, DIN);

        // Rhythm section (from IKAOPLL_tb.sv)
        `define AD #150
        `define DD #800

        `DD IKAOPLL_write(1'b0, 8'h16, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'h20, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h17, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'h50, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h18, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'hC0, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h26, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'h05, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h27, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'h05, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h28, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'h01, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b0, 8'h0E, phiMref, CS_n, WR_n, A0, DIN);
        #100 IKAOPLL_write(1'b1, 8'h30, phiMref, CS_n, WR_n, A0, DIN);

        // simple inst test (shortened from original)
        `DD IKAOPLL_write(1'b0, 8'h10, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'hAC, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h30, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'hE0, phiMref, CS_n, WR_n, A0, DIN);
        `DD IKAOPLL_write(1'b0, 8'h20, phiMref, CS_n, WR_n, A0, DIN);
        `AD IKAOPLL_write(1'b1, 8'h17, phiMref, CS_n, WR_n, A0, DIN);

        // let it ring for a while
        #2_000_000; // simulation time (~20 ms in 10ps units)

        // ---- END pattern ----

        $display("[TB] Phase1 pattern done, finishing.");
        //$fclose(fh_samples);
        $finish;
    end

    // ============================================================
    // 8. Global timeout (finish after fixed simulation time)
    // ============================================================
    initial begin
        // ここでシミュレーション時間を指定（単位は timescale=10ps）
        // 例: 0.5秒相当 → 0.5 / (10ps) = 0.5 / 1e-11 = 5e10 ticks
        //    #5_000_000_000 は 0.05秒、#50_000_000_000 で 0.5秒くらい
        #50_000_000_000;
        $display("[TB] Global timeout reached, finishing.");
        //$fclose(fh_samples);
        $finish;
    end
endmodule