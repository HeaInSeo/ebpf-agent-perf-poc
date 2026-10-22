package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
)

func fixture(t *testing.T, n, bytesPerFile int) (string, string) {
	t.Helper()
	root := t.TempDir()
	in, out := filepath.Join(root, "in"), filepath.Join(root, "out")
	if err := os.Mkdir(in, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(out, 0700); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < n; i++ {
		contents := bytes.Repeat([]byte{byte(i % 251)}, bytesPerFile)
		if err := os.WriteFile(filepath.Join(in, fmt.Sprintf("item-%04d.bin", i)), contents, 0600); err != nil {
			t.Fatal(err)
		}
	}
	return in, out
}
func TestCopyVariantsSameBytes(t *testing.T) {
	for _, shape := range []string{"chain", "fanout"} {
		for _, workers := range []int{1, 4} {
			for _, variant := range []string{"readall", "buffered", "optimized"} {
				t.Run(fmt.Sprintf("%s_%d_%s", shape, workers, variant), func(t *testing.T) {
					in, out := fixture(t, 7, 16385)
					r, err := execute(config{variant: variant, shape: shape, inputDir: in, outputDir: out, nodes: 7, workers: workers})
					if err != nil {
						t.Fatal(err)
					}
					if !r["success"].(bool) || r["completed"].(int64) != 7 {
						t.Fatal(r)
					}
					for i := 0; i < 7; i++ {
						name := fmt.Sprintf("item-%04d.bin", i)
						a, err := os.ReadFile(filepath.Join(in, name))
						if err != nil {
							t.Fatal(err)
						}
						b, err := os.ReadFile(filepath.Join(out, name))
						if err != nil {
							t.Fatal(err)
						}
						if sha256.Sum256(a) != sha256.Sum256(b) {
							t.Fatalf("mismatch %s", name)
						}
					}
				})
			}
		}
	}
}
func TestPrecancelledTaskAndInvalidRuns(t *testing.T) {
	in, out := fixture(t, 1, 4096)
	var done, total atomic.Int64
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	r := &copyTask{source: filepath.Join(in, "item-0000.bin"), dest: filepath.Join(out, "item-0000.bin"), variant: "optimized", completed: &done, totalBytes: &total}
	if err := r.RunE(ctx, nil); err == nil {
		t.Fatal("cancelled task returned nil")
	}
	if done.Load() != 0 {
		t.Fatal("cancelled task executed")
	}
	for _, bad := range []config{
		{variant: "unknown", shape: "chain", inputDir: in, outputDir: out, nodes: 1, workers: 1},
		{variant: "buffered", shape: "cycle", inputDir: in, outputDir: out, nodes: 1, workers: 1},
		{variant: "buffered", shape: "chain", inputDir: in, outputDir: out, nodes: 0, workers: 1},
	} {
		if _, err := execute(bad); err == nil {
			t.Fatalf("accepted invalid config %+v", bad)
		}
	}
	if _, err := execute(config{variant: "optimized", shape: "fanout", inputDir: in, outputDir: out, nodes: 2, workers: 1}); err == nil {
		t.Fatal("expected missing input failure")
	}
}
