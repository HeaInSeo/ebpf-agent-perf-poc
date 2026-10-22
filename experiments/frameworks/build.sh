#!/usr/bin/env bash
set -Eeuo pipefail
framework=${1:?framework required}
root=$(cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$root/build"
gcc -Wall -Wextra -Werror -O2 "$root/target.c" -o "$root/build/target"
case "$framework" in
  bpftrace) bpftrace --version ;;
  bcc) /usr/bin/python3 -c 'import bcc; print("bcc:", bcc.__version__)' ;;
  libbpf|cilium)
    clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu \
      -c "$root/counter.bpf.c" -o "$root/build/counter.bpf.o"
    if test "$framework" = libbpf; then
      gcc -Wall -Wextra -Werror -O2 "$root/libbpf.c" -o "$root/build/libbpf" $(pkg-config --cflags --libs libbpf)
    else
      cd "$root/cilium"
      go mod download
      go mod verify
      go vet ./...
      go build -mod=readonly -trimpath -o "$root/build/cilium" .
      go version -m "$root/build/cilium"
    fi ;;
  aya)
    cargo +nightly-2025-09-01 install bpf-linker --version 0.9.15 --locked
    cargo +nightly-2025-09-01 build --locked --manifest-path "$root/aya-user/Cargo.toml" --release
    cargo +nightly-2025-09-01 build --manifest-path "$root/aya-ebpf/Cargo.toml" \
      --target bpfel-unknown-none -Z build-std=core --release --locked
    cp "$root/aya-user/target/release/framework-aya" "$root/build/aya"
    cp "$root/aya-ebpf/target/bpfel-unknown-none/release/framework-counter" "$root/build/aya-counter"
    rustc +nightly-2025-09-01 -vV
    bpf-linker --version ;;
  *) echo "unknown framework" >&2; exit 2 ;;
esac
sha256sum "$root"/build/*
