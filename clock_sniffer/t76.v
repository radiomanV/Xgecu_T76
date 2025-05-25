module clock_sniffer (
	// Clock
    input wire i_clock_20M, i_clock_80M,    
	
	// Shift register pins
    output wire ser_clk, ser_data, vpp_le, vcc_le, gnd_le, vpp_oe, vcc_oe, gnd_oe,	
    
	// ISP power pins   	
	output wire j_vpp_24, j_vpp_26, j_vcc_04, j_vcc_20, j_vcc_22, j_vcc_24,    
			    j_gnd_11, j_gnd_21, j_gnd_26, j_gnd_27, j_gnd_28,
    
	// ZIF pins    
    inout wire zif_01, zif_02, zif_03, zif_04, zif_05, zif_06, zif_07, zif_08, zif_09,	
 			   zif_10, zif_11, zif_12, zif_13, zif_14, zif_15, zif_16, zif_17, zif_18,    
			   zif_19, zif_20, zif_21, zif_22, zif_23, zif_24, zif_25, zif_26, zif_27, 			   
			   zif_28, zif_29, zif_30, zif_31, zif_32, zif_33, zif_34, zif_35, zif_36,			   
 			   zif_37, zif_38, zif_39, zif_40, zif_41, zif_42, zif_43, zif_44, zif_45,			   
			   zif_46, zif_47, zif_48,     
        
	// ISP pins 
	inout wire j_02, j_03, j_04, j_05, j_06, j_07, j_08, j_09, j_10, j_11, j_12,j_13,	
			   j_14, j_16, j_17, j_18, j_19, j_20, j_21, j_22, j_23, j_24,	j_25, j_26,	
			   j_27, j_28
);

    // 16 bit counter
    reg [15:0] counter = 0;
    reg clk = 0;

    // Divide 20 MHz clock by 20,000 (10,000 clocks * 2 counter togles)
    always @(posedge i_clock_20M) begin
        if (counter == 9999) begin  // 10,000 clocks
            counter <= 0;
            clk <= ~clk;
        end else begin
            counter <= counter + 1;
        end
    end
        
	// Default (off) j_gnd pin drivers
	assign j_gnd_11=0, j_gnd_21=0, j_gnd_26=0, j_gnd_27=1, j_gnd_28=1;	 

    // output the 1KHz signal to whatever
	/*
	assign	j_02=clk, j_03=clk, j_04=clk, j_05=clk, j_06=clk;
	assign	j_07=clk, j_08=clk, j_09=clk, j_10=clk, j_11=clk, j_12=clk;
	assign	j_13=clk, j_14=clk, j_16=clk, j_17=clk, j_18=clk;
	assign	j_19=clk, j_20=clk, j_21=clk, j_22=clk, j_23=clk, j_24=clk;
	assign	j_25=clk, j_26=clk, j_27=clk, j_28=clk;	
	*/	
	
/*
    assign zif_01=clk, zif_02=clk, zif_03=clk, zif_04=clk, zif_05=clk, zif_06=clk, zif_07=clk;
    assign zif_08=clk, zif_09=clk, zif_10=clk, zif_11=clk, zif_12=clk, zif_13=clk, zif_14=clk, zif_15=clk;
    assign zif_16=clk, zif_17=clk, zif_18=clk, zif_19=clk, zif_20=clk, zif_21=clk, zif_22=clk, zif_23=clk;
    assign zif_24=clk, zif_25=clk, zif_26=clk, zif_27=clk, zif_28=clk, zif_29=clk, zif_30=clk, zif_31=clk;
    assign zif_32=clk, zif_33=clk, zif_34=clk, zif_35=clk, zif_36=clk, zif_37=clk, zif_38=clk, zif_39=clk;
    assign zif_40=clk, zif_41=clk, zif_42=clk, zif_43=clk, zif_44=clk, zif_45=clk, zif_46=clk, zif_47=clk;
    assign zif_48=clk;
*/    

	assign j_19=clk;
		
endmodule

