"""Guard against false PASS results without loading anything into the kernel."""

import contextlib
import io
import os
import unittest
from unittest.mock import patch

from run import collect_events, is_target_event, validate_result


class EvidenceChecks(unittest.TestCase):
    def test_accepts_only_matching_kernel_payload(self):
        line = "python3-4242 [001] .... 12.3: bpf_trace_printk: Hello World! pid=4242 cookie=9876"
        self.assertTrue(is_target_event(line, 4242, 9876))
        self.assertFalse(is_target_event(line, 1111, 9876))
        self.assertFalse(is_target_event(line, 4242, 1234))
        self.assertFalse(is_target_event("[setup] Hello World!", 4242, 9876))
        self.assertFalse(is_target_event(line + " unexpected", 4242, 9876))

    def test_zero_or_duplicate_events_cannot_pass(self):
        for events in ([], ["event", "event"]):
            with self.subTest(events=events), self.assertRaises(RuntimeError):
                validate_result(events, 0, 0, True)

    def test_process_or_cleanup_failure_cannot_pass(self):
        for target, loader, detached in ((1, 0, True), (0, 1, True), (0, 0, False), (None, 0, True)):
            with self.subTest(target=target, loader=loader, detached=detached), self.assertRaises(RuntimeError):
                validate_result(["event"], target, loader, detached)

    def test_one_event_and_clean_exit_pass(self):
        validate_result(["event"], 0, 0, True)

    def test_nonblocking_data_is_read_even_without_poll_notification(self):
        reader, writer = os.pipe()
        try:
            os.set_blocking(reader, False)
            os.write(writer, b"task-42 [001] .... 1.0: bpf_trace_printk: Hello World! pid=42 cookie=99\n")
            with patch("run.select.select", return_value=([], [], [])), contextlib.redirect_stdout(io.StringIO()):
                events = collect_events(reader, 42, 99, io.StringIO(), 0.01)
            self.assertEqual(len(events), 1)
        finally:
            os.close(reader)
            os.close(writer)


if __name__ == "__main__":
    unittest.main()
