#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

/* Linux x86_64 raw_syscalls:sys_enter: common header, id, six args. */
struct syscall_event { unsigned long common; long id; unsigned long args[6]; };
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u32);
} CONFIG SEC(".maps");
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} COUNTS SEC(".maps");

SEC("tracepoint/raw_syscalls/sys_enter")
int count_getpid(struct syscall_event *ctx) {
    __u32 key = 0;
    __u32 *target = bpf_map_lookup_elem(&CONFIG, &key);
    if (!target || (bpf_get_current_pid_tgid() >> 32) != *target || ctx->id != 39)
        return 0;
    __u64 *count = bpf_map_lookup_elem(&COUNTS, &key);
    if (count) __sync_fetch_and_add(count, 1);
    return 0;
}
char LICENSE[] SEC("license") = "Dual MIT/GPL";
