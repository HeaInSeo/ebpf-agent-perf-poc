// costbench isolates the explicit buffered file-copy path used by iobench.
// The upstream DAG library is not involved in this deliberately narrow study.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"runtime"
	"runtime/pprof"
	"runtime/trace"
	"syscall"
	"time"
)

func copyStream(ctx context.Context, dst io.Writer, src io.Reader, buf []byte) (int64, error) {
	var total int64
	for {
		if err := ctx.Err(); err != nil {
			return total, err
		}
		n, err := src.Read(buf)
		if n > 0 {
			m, we := dst.Write(buf[:n])
			total += int64(m)
			if we != nil {
				return total, we
			}
			if m != n {
				return total, io.ErrShortWrite
			}
		}
		if errors.Is(err, io.EOF) {
			return total, nil
		}
		if err != nil {
			return total, err
		}
	}
}

func cpuNS() int64 {
	var u syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &u); err != nil {
		panic(err)
	}
	return (u.Utime.Sec+u.Stime.Sec)*1e9 + (u.Utime.Usec+u.Stime.Usec)*1e3
}

func run() error {
	in := flag.String("input", "", "input file")
	out := flag.String("output", "", "output file")
	chunk := flag.Int("chunk", 32768, "32768 or 65536")
	iterations := flag.Int("iterations", 1, "number of complete copies")
	prof := flag.String("profile", "", "profile file prefix; empty disables Go profiling")
	flag.Parse()
	if (*chunk != 32768 && *chunk != 65536) || *iterations < 0 {
		return errors.New("invalid configuration")
	}
	src, err := os.Open(*in)
	if err != nil {
		return err
	}
	defer src.Close()
	dst, err := os.Create(*out)
	if err != nil {
		return err
	}
	defer dst.Close()
	st, err := src.Stat()
	if err != nil {
		return err
	}
	enc := json.NewEncoder(os.Stdout)
	if err := enc.Encode(map[string]any{"ready": true, "pid": os.Getpid(), "read_fd": src.Fd(), "write_fd": dst.Fd()}); err != nil {
		return err
	}
	stdin := bufio.NewScanner(os.Stdin)
	if !stdin.Scan() || stdin.Text() != "GO" {
		return errors.New("GO handshake missing")
	}
	if *prof != "" {
		cf, err := os.Create(*prof + ".cpu.pprof")
		if err != nil {
			return err
		}
		if err := pprof.StartCPUProfile(cf); err != nil {
			cf.Close()
			return err
		}
		defer cf.Close()
		defer pprof.StopCPUProfile()
		tf, err := os.Create(*prof + ".runtime.trace")
		if err != nil {
			return err
		}
		if err := trace.Start(tf); err != nil {
			tf.Close()
			return err
		}
		defer tf.Close()
		defer trace.Stop()
	}
	buf := make([]byte, *chunk)
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	cpu := cpuNS()
	start := time.Now()
	var total int64
	for i := 0; i < *iterations; i++ {
		if _, err := src.Seek(0, io.SeekStart); err != nil {
			return err
		}
		if _, err := dst.Seek(0, io.SeekStart); err != nil {
			return err
		}
		n, err := copyStream(context.Background(), dst, src, buf)
		if err != nil {
			return err
		}
		if n != st.Size() {
			return fmt.Errorf("short copy: %d", n)
		}
		total += n
	}
	duration := time.Since(start).Nanoseconds()
	cpu = cpuNS() - cpu
	runtime.ReadMemStats(&after)
	// Stop profilers before publishing the result, including their flush cost in
	// process measurements but excluding it from hot-path elapsed time.
	if *prof != "" {
		trace.Stop()
		pprof.StopCPUProfile()
	}
	if err := enc.Encode(map[string]any{"success": true, "duration_ns": duration, "cpu_ns": cpu, "bytes": total, "iterations": *iterations, "chunk": *chunk, "alloc_bytes": after.TotalAlloc - before.TotalAlloc, "gc_cycles": after.NumGC - before.NumGC}); err != nil {
		return err
	}
	if !stdin.Scan() || stdin.Text() != "EXIT" {
		return errors.New("EXIT handshake missing")
	}
	return nil
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
