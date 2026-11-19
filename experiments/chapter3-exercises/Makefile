CLANG ?= clang
ARCH_INCLUDE := /usr/include/$(shell uname -m)-linux-gnu
CFLAGS := -target bpf -g -O2 -Wall -Werror -I$(ARCH_INCLUDE)

.PHONY: all clean
all: xdp_pass.bpf.o xdp_abort.bpf.o

%.bpf.o: %.bpf.c
	$(CLANG) $(CFLAGS) -c $< -o $@

clean:
	rm -f xdp_pass.bpf.o xdp_abort.bpf.o
