#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Start idle so attaching the observer never races the measured calls. */
int main(void) {
    char line[64];
    puts("READY");
    fflush(stdout);
    while (fgets(line, sizeof(line), stdin)) {
        char *end;
        long n = strtol(line, &end, 10);
        if (end == line || n < 0 || n > 1000000) return 2;
        for (long i = 0; i < n; i++)
            if (syscall(SYS_getpid) <= 0) return 3;
        printf("DONE %ld\n", n);
        fflush(stdout);
    }
    return 0;
}
