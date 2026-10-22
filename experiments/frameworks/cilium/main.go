package main

import (
	"fmt"
	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/rlimit"
	"os"
	"os/signal"
	"strconv"
	"syscall"
)

func run() error {
	if len(os.Args) != 3 {
		return fmt.Errorf("usage: collector PID OBJECT")
	}
	n, err := strconv.ParseUint(os.Args[1], 10, 32)
	if err != nil {
		return err
	}
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)
	defer signal.Stop(sigs)
	if err := rlimit.RemoveMemlock(); err != nil {
		return err
	}
	spec, err := ebpf.LoadCollectionSpec(os.Args[2])
	if err != nil {
		return err
	}
	coll, err := ebpf.NewCollection(spec)
	if err != nil {
		return fmt.Errorf("load: %w", err)
	}
	defer coll.Close()
	key, pid := uint32(0), uint32(n)
	if err := coll.Maps["CONFIG"].Update(key, pid, ebpf.UpdateAny); err != nil {
		return err
	}
	attached, err := link.Tracepoint("raw_syscalls", "sys_enter", coll.Programs["count_getpid"], nil)
	if err != nil {
		return err
	}
	defer attached.Close()
	fmt.Println("READY")
	<-sigs
	var value uint64
	if err := coll.Maps["COUNTS"].Lookup(key, &value); err != nil {
		return err
	}
	fmt.Printf("{\"observed\":%d}\n", value)
	return nil
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
