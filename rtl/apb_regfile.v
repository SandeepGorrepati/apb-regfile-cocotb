`timescale 1ns/1ps
// AMBA APB4 slave: 8x32-bit register file with error response (PSLVERR).
// Two-phase SETUP/ACCESS protocol. PRDATA and PSLVERR are valid combinationally
// during the ACCESS phase (psel & penable); register state updates sequentially.
//
// Address map (PADDR[4:2] selects the word):
//   0x00 SCRATCH0 RW | 0x04 SCRATCH1 RW | 0x08 SCRATCH2 RW | 0x0C SCRATCH3 RW
//   0x10 CONTROL  RW | 0x14 STATUS   RW | 0x18 ID  RO (write->PSLVERR, reset 0xC0DE0001)
//   0x1C SCRATCH7 RW
// Any PADDR >= 0x20 -> PSLVERR (address-decode error path).
module apb_regfile #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 32
)(
    input  wire                   pclk,
    input  wire                   presetn,
    input  wire                   psel,
    input  wire                   penable,
    input  wire                   pwrite,
    input  wire [ADDR_WIDTH-1:0]  paddr,
    input  wire [DATA_WIDTH-1:0]  pwdata,
    output wire [DATA_WIDTH-1:0]  prdata,
    output wire                   pready,
    output wire                   pslverr
);
    reg [DATA_WIDTH-1:0] regs [0:7];

    wire [2:0] widx    = paddr[4:2];
    wire       inrange = (paddr < 8'h20);
    wire       is_id   = (widx == 3'd6);   // ID register is read-only
    wire       access  = psel & penable;

    assign pready  = 1'b1;                  // zero wait states
    assign prdata  = inrange ? regs[widx] : 32'h0;
    assign pslverr = access & ( (!inrange) | (pwrite & is_id) );

    integer i;
    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            for (i = 0; i < 8; i = i + 1) regs[i] <= 32'h0;
            regs[6] <= 32'hC0DE_0001;       // ID reset value
        end else if (access && pwrite && inrange && !is_id) begin
            regs[widx] <= pwdata;
        end
    end
endmodule
