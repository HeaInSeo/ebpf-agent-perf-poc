"""Guard against false PASS results without loading anything into the kernel."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from run import Blocked, collect_events, configure_target_cpu, is_target_event, validate_result
from verify_cpus import assess_trial, main as verify_cpus_main


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


class CpuChecks(unittest.TestCase):
    def test_affinity_is_applied_and_read_back(self):
        with patch("run.os.sched_getaffinity", side_effect=[{0, 1, 2, 3}, {2}]), \
             patch("run.os.sched_setaffinity") as setter:
            self.assertEqual(configure_target_cpu(4242, 2), [2])
            setter.assert_called_once_with(4242, {2})

    def test_disallowed_cpu_is_rejected_before_setting_affinity(self):
        with patch("run.os.sched_getaffinity", return_value={0, 1}), \
             patch("run.os.sched_setaffinity") as setter:
            with self.assertRaises(Blocked):
                configure_target_cpu(4242, 2)
            setter.assert_not_called()

    def test_failed_affinity_readback_is_rejected(self):
        with patch("run.os.sched_getaffinity", side_effect=[{0, 1}, {0, 1}]), \
             patch("run.os.sched_setaffinity"):
            with self.assertRaises(RuntimeError):
                configure_target_cpu(4242, 1)


class CpuEvidenceChecks(unittest.TestCase):
    SHA = "a" * 40

    def setUp(self):
        self.env = {"source_sha": self.SHA}
        self.result = {
            "status": "PASS", "reason": "정상 종료함", "attached": True,
            "target_pid": 4242, "cookie": 9876, "target_cpu": 2, "target_affinity": [2],
            "expected_events": 1, "received_events": 1,
            "events": ["python3-4242 [002] .... 12.3: bpf_trace_printk: Hello World! pid=4242 cookie=9876"],
            "target_exit": 0, "loader_exit": 0, "detached": True,
        }

    def empty_control(self):
        result = copy.deepcopy(self.result)
        result.update(status="FAIL", events=[], received_events=0)
        try:
            validate_result([], 0, 0, True)
        except RuntimeError as exc:
            result["reason"] = str(exc)
        return result

    def test_actual_message_on_requested_cpu_passes(self):
        for mode in ("raw", "typed"):
            with self.subTest(mode=mode):
                self.assertEqual(assess_trial(mode, 2, 0, self.result, self.env, self.SHA), "PASS")

    def test_only_typed_control_can_record_zero_messages(self):
        result = self.empty_control()
        self.assertEqual(assess_trial("typed", 2, 1, result, self.env, self.SHA), "NO_EVENT")
        with self.assertRaises((ValueError, RuntimeError)):
            assess_trial("raw", 2, 1, result, self.env, self.SHA)

    def test_wrong_cpu_or_payload_cannot_pass(self):
        for change in (("[002]", "[000]"), ("pid=4242", "pid=9999"), ("cookie=9876", "cookie=1")):
            result = copy.deepcopy(self.result)
            result["events"][0] = result["events"][0].replace(*change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess_trial("raw", 2, 0, result, self.env, self.SHA)

    def test_duplicate_message_cannot_pass(self):
        result = copy.deepcopy(self.result)
        result["events"] *= 2
        result["received_events"] = 2
        with self.assertRaises(RuntimeError):
            assess_trial("raw", 2, 0, result, self.env, self.SHA)

    def test_control_infrastructure_errors_are_not_excused(self):
        for key, value in (("attached", False), ("target_exit", 1), ("loader_exit", 1),
                           ("detached", False), ("reason", "추적 설정 복원 오류"),
                           ("target_affinity", [0, 2])):
            result = self.empty_control()
            result[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess_trial("typed", 2, 1, result, self.env, self.SHA)

    def test_source_mismatch_and_timeout_cannot_pass(self):
        with self.assertRaises(ValueError):
            assess_trial("raw", 2, 0, self.result, {"source_sha": "b" * 40}, self.SHA)
        with self.assertRaises(ValueError):
            assess_trial("typed", 2, 1, self.empty_control(), self.env, self.SHA, timed_out=True)


class CpuCoverageChecks(unittest.TestCase):
    def test_more_than_eight_cpus_is_blocked_without_partial_execution(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("verify_cpus.os.sched_getaffinity", return_value=set(range(9))), \
             patch("verify_cpus.run_trial") as trial, \
             patch("sys.argv", ["verify_cpus.py", "--output", directory]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify_cpus_main(), 1)
            trial.assert_not_called()
            result = json.loads((Path(directory) / "result.json").read_text())
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["allowed_cpus"], list(range(9)))
            self.assertEqual(result["raw_passed"], 0)
            self.assertEqual(result["raw_expected"], 18)


if __name__ == "__main__":
    unittest.main()
