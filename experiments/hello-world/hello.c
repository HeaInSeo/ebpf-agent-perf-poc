/*
 * Adapted from HeaInSeo/ebpf-study at
 * 9b9da7308f13828f557ec5c05e5aff663da4e7b4, c-libbpf/src/hello.c.
 * 연결 완료 알림과 종료 제한을 추가한 GitHub Actions용 libbpf 로더.
 */
#define _POSIX_C_SOURCE 200809L

#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct hello_config_value {
    __u32 pid;
    __u32 pad;
    __u64 cookie;
};

_Static_assert(sizeof(struct hello_config_value) == 16,
               "hello_config must match the BPF map value");

static volatile sig_atomic_t exiting;
static volatile sig_atomic_t timed_out;

static void handle_signal(int signal_number)
{
    if (signal_number == SIGALRM)
        timed_out = 1;
    else
        exiting = 1;
}

static int parse_positive_decimal(const char *text, uint64_t maximum,
                                  uint64_t *value)
{
    char *end;
    unsigned long long parsed;

    if (text[0] == '\0')
        return -1;
    for (const char *cursor = text; *cursor; cursor++) {
        if (*cursor < '0' || *cursor > '9')
            return -1;
    }
    errno = 0;
    parsed = strtoull(text, &end, 10);
    if (errno != 0 || *end != '\0' || parsed == 0 || parsed > maximum)
        return -1;
    *value = (uint64_t)parsed;
    return 0;
}

int main(int argc, char **argv)
{
    struct bpf_object *object = NULL;
    struct bpf_program *program;
    struct bpf_link *link = NULL;
    struct hello_config_value config = {0};
    struct sigaction action = {0};
    sigset_t blocked, previous_mask, wait_mask;
    uint64_t target_pid, cookie;
    __u32 key = 0;
    bool mask_installed = false;
    bool detached = false;
    int map_fd;
    int result = EXIT_FAILURE;
    long error;

    if (argc != 4 ||
        parse_positive_decimal(argv[2], UINT32_MAX, &target_pid) != 0 ||
        parse_positive_decimal(argv[3], INT64_MAX, &cookie) != 0) {
        fprintf(stderr, "Usage: %s OBJECT_PATH TARGET_PID COOKIE\n", argv[0]);
        fprintf(stderr, "PID must be positive uint32; COOKIE must be positive int64.\n");
        return EXIT_FAILURE;
    }

    /* 종료 요청을 놓치지 않도록 신호 차단과 대기를 원자적으로 전환한다. */
    sigemptyset(&blocked);
    sigaddset(&blocked, SIGINT);
    sigaddset(&blocked, SIGTERM);
    sigaddset(&blocked, SIGALRM);
    if (sigprocmask(SIG_BLOCK, &blocked, &previous_mask) != 0) {
        perror("sigprocmask");
        goto cleanup;
    }
    mask_installed = true;
    action.sa_handler = handle_signal;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) != 0 ||
        sigaction(SIGTERM, &action, NULL) != 0 ||
        sigaction(SIGALRM, &action, NULL) != 0) {
        perror("sigaction");
        goto cleanup;
    }
    alarm(30);

    object = bpf_object__open_file(argv[1], NULL);
    error = libbpf_get_error(object);
    if (error != 0) {
        object = NULL;
        fprintf(stderr, "Cannot open BPF object %s: %s\n", argv[1], strerror((int)-error));
        goto cleanup;
    }
    error = bpf_object__load(object);
    if (error != 0) {
        fprintf(stderr, "Cannot load BPF program: %s (see libbpf/verifier log above)\n",
                strerror((int)-error));
        goto cleanup;
    }

    /* 연결 전에 관찰 대상과 이번 실행의 식별값을 맵에 넣는다. */
    map_fd = bpf_object__find_map_fd_by_name(object, "hello_config");
    if (map_fd < 0) {
        fprintf(stderr, "Cannot find hello_config map: %s\n", strerror(-map_fd));
        goto cleanup;
    }
    config.pid = (__u32)target_pid;
    config.cookie = cookie;
    if (bpf_map_update_elem(map_fd, &key, &config, BPF_ANY) != 0) {
        fprintf(stderr, "Cannot set hello_config: %s\n", strerror(errno));
        goto cleanup;
    }
    program = bpf_object__find_program_by_name(object, "hello");
    if (program == NULL) {
        fprintf(stderr, "Cannot find BPF program named hello\n");
        goto cleanup;
    }
    link = bpf_program__attach(program);
    error = libbpf_get_error(link);
    if (error != 0) {
        link = NULL;
        fprintf(stderr, "Cannot attach execve tracepoint: %s\n", strerror((int)-error));
        goto cleanup;
    }

    /* 이 알림을 받은 뒤에만 테스트 프로세스가 execve를 실행한다. */
    printf("READY pid=%" PRIu32 " cookie=%" PRIu64 "\n",
           (uint32_t)config.pid, (uint64_t)config.cookie);
    if (fflush(stdout) != 0) {
        perror("flush READY");
        goto cleanup;
    }

    wait_mask = previous_mask;
    sigdelset(&wait_mask, SIGINT);
    sigdelset(&wait_mask, SIGTERM);
    sigdelset(&wait_mask, SIGALRM);
    while (!exiting && !timed_out)
        sigsuspend(&wait_mask);

    if (timed_out)
        fprintf(stderr, "Loader timed out after 30 seconds\n");
    else
        result = EXIT_SUCCESS;

cleanup:
    alarm(0);
    if (link != NULL) {
        error = bpf_link__destroy(link);
        link = NULL;
        if (error != 0) {
            fprintf(stderr, "Cannot detach BPF link: %s\n", strerror((int)-error));
            result = EXIT_FAILURE;
        } else {
            detached = true;
        }
    }
    bpf_object__close(object);
    if (detached) {
        printf("DETACHED\n");
        if (fflush(stdout) != 0)
            result = EXIT_FAILURE;
    }
    if (mask_installed && sigprocmask(SIG_SETMASK, &previous_mask, NULL) != 0) {
        perror("restore signal mask");
        result = EXIT_FAILURE;
    }
    return result;
}
