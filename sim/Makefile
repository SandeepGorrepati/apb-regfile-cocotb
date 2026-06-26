# Classic cocotb Makefile flow (alternative to runner.py).
#   make            # run all tests with Icarus Verilog
#   make SIM=verilator
TOPDIR := $(shell cd .. && pwd)
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES = $(TOPDIR)/rtl/apb_regfile.v
TOPLEVEL = apb_regfile
MODULE   = test_apb_regfile
export PYTHONPATH := $(TOPDIR)/tb:$(PYTHONPATH)
include $(shell cocotb-config --makefiles)/Makefile.sim
