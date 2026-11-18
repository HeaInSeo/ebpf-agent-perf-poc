"""Guard against false PASS results without loading anything into the kernel."""

import unittest

from run import is_target_event, validate_result


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


if __name__ == "__main__":
    unittest.main()
