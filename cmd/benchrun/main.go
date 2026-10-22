package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	dag "github.com/HeaInSeo/dag-go"
	"os"
	"runtime"
	"runtime/debug"
	"runtime/pprof"
	"sync/atomic"
	"time"
)

type work struct {
	done  *atomic.Int64
	spins int
}

func (w *work) RunE(ctx context.Context, _ interface{}) error {
	var v uint64
	for i := 0; i < w.spins; i++ {
		if i%1024 == 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}
		}
		v += uint64(i*3 + 1)
	}
	if v == ^uint64(0) {
		panic("unreachable")
	}
	w.done.Add(1)
	return nil
}

type result struct {
	Shape           string `json:"shape"`
	Nodes           int    `json:"nodes"`
	Workers         int    `json:"workers"`
	Spins           int    `json:"spins"`
	DurationNS      int64  `json:"duration_ns"`
	Executed        int64  `json:"executed"`
	TotalAllocBytes uint64 `json:"total_alloc_bytes"`
	NumGC           uint32 `json:"num_gc"`
	MaxRSSKB        int64  `json:"max_rss_kb"`
	Goroutines      int    `json:"goroutines"`
	Success         bool   `json:"success"`
}

func run(shape string, n, workers, spins int, cpuProfile string) (result, error) {
	if n < 1 || n > 10000 || workers < 1 || workers > 10000 || spins < 1 {
		return result{}, fmt.Errorf("invalid workload parameters")
	}
	if shape != "chain" && shape != "fanout" {
		return result{}, fmt.Errorf("unsupported shape %q", shape)
	}
	d := dag.NewDagWithConfig(dag.DagConfig{WorkerPoolSize: workers, MinChannelBuffer: 5, MaxChannelBuffer: 100})
	if _, err := d.StartDag(); err != nil {
		return result{}, err
	}
	var count atomic.Int64
	d.SetContainerCmd(&work{done: &count, spins: spins})
	prev := dag.StartNode
	for i := 0; i < n; i++ {
		id := fmt.Sprintf("task-%05d", i)
		from := dag.StartNode
		if shape == "chain" {
			from = prev
		}
		if err := d.AddEdge(from, id); err != nil {
			return result{}, err
		}
		prev = id
	}
	if err := d.FinishDag(); err != nil {
		return result{}, err
	}
	d.ConnectRunner()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	d.GetReady(ctx)
	// Force stable Go memory statistics, but keep it outside the timed region.
	runtime.GC()
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	var f *os.File
	var err error
	if cpuProfile != "" {
		f, err = os.Create(cpuProfile)
		if err != nil {
			return result{}, err
		}
		defer f.Close()
		if err = pprof.StartCPUProfile(f); err != nil {
			return result{}, err
		}
		defer pprof.StopCPUProfile()
	}
	start := time.Now()
	d.Start()
	success := d.Wait(ctx)
	elapsed := time.Since(start)
	runtime.ReadMemStats(&after)
	r := result{Shape: shape, Nodes: n, Workers: workers, Spins: spins, DurationNS: elapsed.Nanoseconds(), Executed: count.Load(), TotalAllocBytes: after.TotalAlloc - before.TotalAlloc, NumGC: after.NumGC - before.NumGC, Goroutines: runtime.NumGoroutine(), Success: success && count.Load() == int64(n)}
	if !r.Success {
		return r, fmt.Errorf("run invalid: dagSuccess=%v executed=%d expected=%d", success, r.Executed, n)
	}
	return r, nil
}
func main() {
	shape := flag.String("shape", "fanout", "chain or fanout")
	nodes := flag.Int("nodes", 100, "number of task nodes")
	workers := flag.Int("workers", 8, "concurrent RunE limit")
	spins := flag.Int("spins", 10000, "deterministic CPU iterations per task")
	cpu := flag.String("cpuprofile", "", "optional Go CPU profile path")
	flag.Parse()
	_ = debug.SetGCPercent(100)
	r, err := run(*shape, *nodes, *workers, *spins, *cpu)
	if e := json.NewEncoder(os.Stdout).Encode(r); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
