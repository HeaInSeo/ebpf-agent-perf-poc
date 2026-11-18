/*
 * Adapted from HeaInSeo/ebpf-study at
 * 9b9da7308f13828f557ec5c05e5aff663da4e7b4, c-libbpf/src/hello.bpf.c.
 * CI에서 이번 실험의 프로세스만 관찰하도록 PID와 실행 식별값을 추가함.
 */
#include <asm/unistd.h>
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct hello_config_value {
    __u32 pid;
    __u32 pad;
    __u64 cookie;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct hello_config_value);
} hello_config SEC(".maps");

#ifdef HELLO_LEGACY_TYPED
/* Ubuntu 7.0의 syscall tracepoint 회귀를 비교하기 위한 기존 연결 방식임. */
SEC("tracepoint/syscalls/sys_enter_execve")
#else
/* syscall별 perf 경로를 거치지 않고 execve 진입만 직접 선택함. */
SEC("raw_tracepoint/sys_enter")
#endif
int hello(void *ctx)
{
    __u32 key = 0;
    __u32 pid = bpf_get_current_pid_tgid() >> 32;
    const struct hello_config_value *config;

#ifdef HELLO_LEGACY_TYPED
    (void)ctx;
#else
    struct bpf_raw_tracepoint_args *args = ctx;

    if (args->args[1] != __NR_execve)
        return 0;
#endif
    config = bpf_map_lookup_elem(&hello_config, &key);
    if (!config || pid != config->pid)
        return 0;

    /* 이 메시지는 커널의 trace_pipe에서 읽음. */
    bpf_printk("Hello World! pid=%u cookie=%llu", pid,
               (unsigned long long)config->cookie);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";
