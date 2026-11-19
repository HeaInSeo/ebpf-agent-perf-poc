#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

/* Exercise 4: XDP_ABORTED == 0; NEVER attach to a host interface. */
SEC("xdp")
int xdp_ch3_abort(struct xdp_md *ctx)
{
    (void)ctx;
    return XDP_ABORTED;
}

char LICENSE[] SEC("license") = "GPL";
