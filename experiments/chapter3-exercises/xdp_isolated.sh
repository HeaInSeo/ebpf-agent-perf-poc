#!/usr/bin/env bash
# Chapter 3 exercises 1 and 4: disposable namespaces, never host eth0.
set -euo pipefail
umask 022

if [[ "$#" -ne 1 ]] || [[ ! -d "$1" ]]; then
  echo "Usage: xdp_isolated.sh <existing results-dir>" >&2
  exit 2
fi
if [[ "$(id -u)" -ne 0 || "$GITHUB_ACTIONS" != "true" || "$RUNNER_ENVIRONMENT" != "github-hosted" ]]; then
  echo "REFUSED: requires root on GitHub-hosted Actions runner" >&2
  exit 2
fi

out="$(realpath "$1")"
src="$(cd "$(dirname "$0")" && pwd)"
pass_obj="$src/xdp_pass.bpf.o"
abort_obj="$src/xdp_abort.bpf.o"
test -f "$pass_obj" && test -f "$abort_obj"
test "$(uname -m)" = "x86_64"

# Namespace names and interface names are unambiguous and disposable.
ns_a="ch3a$$"
ns_b="ch3b$$"
if_a="cxpa"
if_b="cxpb"

cleanup() {
  local exit_status=$?
  set +e
  ip -n "$ns_b" link set dev "$if_b" xdp off >/dev/null 2>&1
  ip netns del "$ns_a" >/dev/null 2>&1
  ip netns del "$ns_b" >/dev/null 2>&1
  echo "CLEANUP: isolated namespaces removed (prior exit=$exit_status)"
}
trap cleanup EXIT

echo "SAFETY: only $ns_a/$ns_b and $if_a/$if_b; no host interfaces touched"
ip netns add "$ns_a"
ip netns add "$ns_b"
ip link add "$if_a" type veth peer name "$if_b"
ip link set "$if_a" netns "$ns_a"
ip link set "$if_b" netns "$ns_b"
ip -n "$ns_a" addr add 10.247.30.1/30 dev "$if_a"
ip -n "$ns_b" addr add 10.247.30.2/30 dev "$if_b"
ip -n "$ns_a" link set lo up
ip -n "$ns_b" link set lo up
ip -n "$ns_a" link set "$if_a" up
ip -n "$ns_b" link set "$if_b" up

ping_peer() { ip netns exec "$ns_a" ping -n -c 2 -W 1 10.247.30.2; }
attached() { ip -n "$ns_b" -details link show dev "$if_b" | grep -q "prog/xdp id"; }
detached() { ! attached; }

echo "=== EX01: XDP_PASS attach -> traffic -> detach ==="
ping_peer
ip -n "$ns_b" link set dev "$if_b" xdp obj "$pass_obj" sec xdp
ip -n "$ns_b" -details link show dev "$if_b" | tee "$out/ex01-link-attached.txt"
attached
ping_peer
ip -n "$ns_b" link set dev "$if_b" xdp off
ip -n "$ns_b" -details link show dev "$if_b" | tee "$out/ex01-link-detached.txt"
detached
ping_peer
echo '{"status":"PASS","checks":["baseline_ping","attached","pass_ping","detached","restored_ping"]}' > "$out/ex01.json"
echo "EX01 PASS: XDP_PASS attached and detached on namespace veth"

echo "=== EX04: XDP_ABORTED(0) drops packets, then restore ==="
ip -n "$ns_b" link set dev "$if_b" xdp obj "$abort_obj" sec xdp
ip -n "$ns_b" -details link show dev "$if_b" | tee "$out/ex04-link-attached.txt"
attached
if ping_peer > "$out/ex04-expected-ping-failure.txt" 2>&1; then
  echo "EX04 FAIL: ping unexpectedly succeeded with XDP_ABORTED" >&2
  exit 1
fi
echo "EX04 observed blocked ping:"
cat "$out/ex04-expected-ping-failure.txt"
ip -n "$ns_b" link set dev "$if_b" xdp off
detached
ping_peer
echo '{"status":"PASS","checks":["attached_abort","blocked_ping","detached","restored_ping"]}' > "$out/ex04.json"
echo "EX04 PASS: XDP_ABORTED blocked isolated traffic; normal traffic restored"
