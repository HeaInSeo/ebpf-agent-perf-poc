#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

/* Exercise 1: harmless ingress XDP program on an isolated veth only. */
SEC("xdp")
int xdp_ch3_pass(struct xdp_md *ctx)
{
    (void)ctx;
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
