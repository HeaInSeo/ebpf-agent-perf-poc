CLANG ?= clang
CC := gcc
PKG_CONFIG ?= pkg-config
BUILD_DIR := build
MULTIARCH := $(shell $(CC) -dumpmachine)

BPF_CFLAGS := -O2 -g -target bpf -Wall -Wextra -Werror -I/usr/include/$(MULTIARCH)
USER_CFLAGS := -O2 -g -std=c11 -Wall -Wextra -Werror

.PHONY: all regression clean

all: $(BUILD_DIR)/hello.bpf.o $(BUILD_DIR)/hello

regression: all $(BUILD_DIR)/hello-typed.bpf.o

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# 커널 자료구조를 읽지 않으므로 생성한 vmlinux.h가 필요하지 않음.
$(BUILD_DIR)/hello.bpf.o: hello.bpf.c | $(BUILD_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

# 원래 syscall별 tracepoint를 동일한 PID·cookie·출력 코드로 대조함.
$(BUILD_DIR)/hello-typed.bpf.o: hello.bpf.c | $(BUILD_DIR)
	$(CLANG) $(BPF_CFLAGS) -DHELLO_LEGACY_TYPED -c $< -o $@

$(BUILD_DIR)/hello: hello.c | $(BUILD_DIR)
	$(CC) $(USER_CFLAGS) $(shell $(PKG_CONFIG) --cflags libbpf) $< -o $@ $(shell $(PKG_CONFIG) --libs libbpf)

clean:
	rm -rf $(BUILD_DIR)
