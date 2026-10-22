package main

import "testing"

func TestWorkloads(t *testing.T) {
	for _, shape := range []string{"chain", "fanout"} {
		for _, workers := range []int{1, 4} {
			r, err := run(shape, 12, workers, 2048, "")
			if err != nil {
				t.Fatalf("shape=%s workers=%d: %v", shape, workers, err)
			}
			if !r.Success || r.Executed != 12 {
				t.Fatalf("bad result %+v", r)
			}
		}
	}
}
func TestInvalidInputs(t *testing.T) {
	for _, v := range []struct {
		shape   string
		n       int
		workers int
		spins   int
	}{
		{"cycle", 10, 1, 100}, {"chain", 0, 1, 100}, {"fanout", 2, 0, 1},
	} {
		if _, err := run(v.shape, v.n, v.workers, v.spins, ""); err == nil {
			t.Fatalf("expected error for %+v", v)
		}
	}
}
