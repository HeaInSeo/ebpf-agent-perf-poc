#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    sigset_t signals;
    sigemptyset(&signals);
    sigaddset(&signals, SIGINT);
    sigaddset(&signals, SIGTERM);
    if (sigprocmask(SIG_BLOCK, &signals, NULL)) return 3;
    uint32_t key = 0, pid = (uint32_t)strtoul(argv[1], NULL, 10);
    struct bpf_object *obj = bpf_object__open_file(argv[2], NULL);
    if (libbpf_get_error(obj)) return 4;
    if (bpf_object__load(obj)) { bpf_object__close(obj); return 5; }
    int cfg = bpf_object__find_map_fd_by_name(obj, "CONFIG");
    int counts = bpf_object__find_map_fd_by_name(obj, "COUNTS");
    if (cfg < 0 || counts < 0 || bpf_map_update_elem(cfg, &key, &pid, BPF_ANY)) {
        bpf_object__close(obj); return 6;
    }
    struct bpf_program *prog = bpf_object__find_program_by_name(obj, "count_getpid");
    if (!prog) { bpf_object__close(obj); return 7; }
    struct bpf_link *link = bpf_program__attach_tracepoint(prog, "raw_syscalls", "sys_enter");
    if (libbpf_get_error(link)) { bpf_object__close(obj); return 8; }
    puts("READY"); fflush(stdout);
    int received;
    int rc = sigwait(&signals, &received);
    uint64_t value = 0;
    if (!rc) rc = bpf_map_lookup_elem(counts, &key, &value);
    bpf_link__destroy(link);
    bpf_object__close(obj);
    if (rc) return 9;
    printf("{\"observed\":%llu}\n", (unsigned long long)value);
    return 0;
}
