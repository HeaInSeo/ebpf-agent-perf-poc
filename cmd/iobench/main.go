package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"runtime/trace"
	"sync/atomic"
	"syscall"
	"time"

	dag "github.com/HeaInSeo/dag-go"
)

type config struct {
	variant, shape, inputDir, outputDir, cpuProfile, runtimeTrace string
	nodes, workers                                                int
}
type copyTask struct {
	source, dest, variant string
	completed, totalBytes *atomic.Int64
}

func (w *copyTask) RunE(ctx context.Context, _ interface{}) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	source, err := os.Open(w.source)
	if err != nil {
		return err
	}
	defer source.Close()
	dest, err := os.OpenFile(w.dest, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}

	var written int64
	switch w.variant {
	case "readall":
		var buf []byte
		buf, err = io.ReadAll(source)
		if err == nil {
			var count int
			count, err = dest.Write(buf)
			written = int64(count)
			if err == nil && count != len(buf) {
				err = io.ErrShortWrite
			}
		}
	case "buffered":
		buf := make([]byte, 32*1024)
		for err == nil {
			var n int
			n, err = source.Read(buf)
			if n > 0 {
				var used int
				used, writeErr := dest.Write(buf[:n])
				written += int64(used)
				if writeErr != nil {
					err = writeErr
				} else if used != n {
					err = io.ErrShortWrite
				}
			}
			if errors.Is(err, io.EOF) {
				err = nil
				break
			}
		}
	case "optimized":
		written, err = io.Copy(dest, source)
	default:
		err = fmt.Errorf("unsupported variant %s", w.variant)
	}
	closeErr := dest.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if err = ctx.Err(); err != nil {
		return err
	}
	w.totalBytes.Add(written)
	w.completed.Add(1)
	return nil
}

func execute(c config) (map[string]any, error) {
	if c.nodes < 1 || c.nodes > 1000 || c.workers < 1 || c.workers > 64 ||
		(c.shape != "chain" && c.shape != "fanout") ||
		(c.variant != "readall" && c.variant != "buffered" && c.variant != "optimized") {
		return nil, fmt.Errorf("invalid shape/variant/nodes/workers")
	}
	if c.inputDir == "" || c.outputDir == "" {
		return nil, errors.New("input/output dirs required")
	}
	if info, err := os.Stat(c.outputDir); err != nil || !info.IsDir() {
		return nil, errors.New("output directory must exist")
	}
	if info, err := os.Stat(c.inputDir); err != nil || !info.IsDir() {
		return nil, errors.New("input directory must exist")
	}
	d := dag.NewDagWithConfig(dag.DagConfig{WorkerPoolSize: c.workers, MinChannelBuffer: 5, MaxChannelBuffer: 128, ExpectedNodeCount: c.nodes + 2})
	if _, err := d.StartDag(); err != nil {
		return nil, err
	}
	var completed, totalBytes atomic.Int64
	prev := dag.StartNode
	for i := 0; i < c.nodes; i++ {
		name := fmt.Sprintf("item-%04d.bin", i)
		nodeID := fmt.Sprintf("node-%04d", i)
		parent := dag.StartNode
		if c.shape == "chain" {
			parent = prev
		}
		if err := d.AddEdge(parent, nodeID); err != nil {
			return nil, err
		}
		if !d.SetNodeRunner(nodeID, &copyTask{source: filepath.Join(c.inputDir, name), dest: filepath.Join(c.outputDir, name), variant: c.variant, completed: &completed, totalBytes: &totalBytes}) {
			return nil, fmt.Errorf("SetNodeRunner rejected %s", nodeID)
		}
		prev = nodeID
	}
	if err := d.FinishDag(); err != nil {
		return nil, err
	}
	if err := d.ConnectRunnerE(); err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	if err := d.GetReadyE(ctx); err != nil {
		return nil, err
	}
	runtime.GC()
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	var traceFile, cpuFile *os.File
	if c.runtimeTrace != "" {
		f, err := os.Create(c.runtimeTrace)
		if err != nil {
			return nil, err
		}
		traceFile = f
		if err := trace.Start(f); err != nil {
			f.Close()
			return nil, err
		}
	}
	if c.cpuProfile != "" {
		f, err := os.Create(c.cpuProfile)
		if err != nil {
			if traceFile != nil {
				trace.Stop()
				traceFile.Close()
			}
			return nil, err
		}
		cpuFile = f
		if err := pprof.StartCPUProfile(f); err != nil {
			f.Close()
			if traceFile != nil {
				trace.Stop()
				traceFile.Close()
			}
			return nil, err
		}
	}
	start := time.Now()
	d.Start()
	waitErr := d.WaitE(ctx)
	duration := time.Since(start)
	if cpuFile != nil {
		pprof.StopCPUProfile()
		cpuFile.Close()
	}
	if traceFile != nil {
		trace.Stop()
		traceFile.Close()
	}
	runtime.ReadMemStats(&after)
	var usage syscall.Rusage
	_ = syscall.Getrusage(syscall.RUSAGE_SELF, &usage)
	success := waitErr == nil && completed.Load() == int64(c.nodes)
	result := map[string]any{
		"variant": c.variant, "shape": c.shape, "nodes": c.nodes, "workers": c.workers,
		"success": success, "completed": completed.Load(), "bytes_copied": totalBytes.Load(),
		"duration_ns": duration.Nanoseconds(), "total_alloc_bytes": after.TotalAlloc - before.TotalAlloc,
		"gc_cycles": after.NumGC - before.NumGC, "process_maxrss_kib": usage.Maxrss,
		"go_version": runtime.Version(),
	}
	if !success {
		return result, fmt.Errorf("DAG failed (completed %d/%d): %w", completed.Load(), c.nodes, waitErr)
	}
	return result, nil
}
func main() {
	dag.Log.SetOutput(io.Discard)
	c := config{}
	flag.StringVar(&c.variant, "variant", "optimized", "readall|buffered|optimized")
	flag.StringVar(&c.shape, "shape", "fanout", "chain|fanout")
	flag.StringVar(&c.inputDir, "input-dir", "", "existing input data directory")
	flag.StringVar(&c.outputDir, "output-dir", "", "existing output data directory")
	flag.IntVar(&c.nodes, "nodes", 16, "input and task count")
	flag.IntVar(&c.workers, "workers", 4, "maximum concurrent DAG tasks")
	flag.StringVar(&c.cpuProfile, "cpuprofile", "", "optional CPU profile (adds overhead)")
	flag.StringVar(&c.runtimeTrace, "trace", "", "optional Go runtime trace (adds overhead)")
	flag.Parse()
	r, err := execute(c)
	if r != nil {
		if e := json.NewEncoder(os.Stdout).Encode(r); e != nil {
			fmt.Fprintln(os.Stderr, e)
			os.Exit(2)
		}
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
