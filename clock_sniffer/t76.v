module clock_sniffer (
    input i_clock_20M, i_clock_80M,
    inout zif_01, zif_02, zif_03, zif_04, zif_05, zif_06, zif_07, zif_08,
    inout zif_09, zif_10, zif_11, zif_12, zif_13, zif_14, zif_15, zif_16,
    inout zif_17, zif_18, zif_19, zif_20, zif_21, zif_22, zif_23, zif_24,
    inout zif_25, zif_26, zif_27, zif_28, zif_29, zif_30, zif_31, zif_32,
    inout zif_33, zif_34, zif_35, zif_36, zif_37, zif_38, zif_39, zif_40,
    inout zif_41, zif_42, zif_43, zif_44, zif_45, zif_46, zif_47, zif_48
);

    // 16 bit counter
    reg [15:0] counter = 0;
    reg q = 0;

    // Divide 20 MHz clock by 20,000 (10,000 clocks * 2 counter togles)
    always @(posedge i_clock_20M) begin
        if (counter == 9999) begin  // 10,000 clocks
            counter <= 0;
            q <= ~q;
        end else begin
            counter <= counter + 1;
        end
    end

    // output the 1KHz signal to zif_48 pin
    assign zif_48 = q;

endmodule

