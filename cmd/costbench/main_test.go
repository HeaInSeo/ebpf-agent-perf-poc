package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"testing"
)

type shortWriter struct{}

func (shortWriter) Write(p []byte) (int, error) { return len(p) - 1, nil }

type brokenReader struct{}

func (brokenReader) Read([]byte) (int, error) { return 0, io.ErrUnexpectedEOF }

type cancelWriter struct {
	cancel context.CancelFunc
	bytes.Buffer
}

func (w *cancelWriter) Write(p []byte) (int, error) { w.cancel(); return w.Buffer.Write(p) }

func TestEquivalentAndFailurePaths(t *testing.T) {
	for _, size := range []int{0, 1, 32767, 32768, 32769, 65536, 65537, 1048583} {
		data := bytes.Repeat([]byte{byte(size % 251)}, size)
		for _, chunk := range []int{32768, 65536} {
			var dst bytes.Buffer
			n, err := copyStream(context.Background(), &dst, bytes.NewReader(data), make([]byte, chunk))
			if err != nil || n != int64(size) || !bytes.Equal(data, dst.Bytes()) {
				t.Fatalf("size=%d chunk=%d n=%d err=%v", size, chunk, n, err)
			}
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := copyStream(ctx, io.Discard, bytes.NewReader([]byte("data")), make([]byte, 2)); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	ctx, cancel = context.WithCancel(context.Background())
	w := &cancelWriter{cancel: cancel}
	if n, err := copyStream(ctx, w, bytes.NewReader([]byte("abcdef")), make([]byte, 2)); n != 2 || !errors.Is(err, context.Canceled) {
		t.Fatalf("mid-copy cancel n=%d err=%v", n, err)
	}
	if _, err := copyStream(context.Background(), shortWriter{}, bytes.NewReader([]byte("data")), make([]byte, 4)); !errors.Is(err, io.ErrShortWrite) {
		t.Fatal(err)
	}
	if _, err := copyStream(context.Background(), io.Discard, brokenReader{}, make([]byte, 4)); !errors.Is(err, io.ErrUnexpectedEOF) {
		t.Fatal(err)
	}
}
