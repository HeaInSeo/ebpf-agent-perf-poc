import unittest
from probe import parse_counter


class CounterEvidenceTests(unittest.TestCase):
    def test_real_first_attempt_duplicate_dump_is_rejected(self):
        # F001 first attempt printed 500 followed by a cleared-map 0.
        with self.assertRaises(ValueError):
            parse_counter("bpftrace", "READY\n@events: 500\n\n@events: 0\n")

    def test_bpftrace_single_snapshot_and_empty_map(self):
        self.assertEqual(parse_counter("bpftrace", "READY\n@events: 500\n"), 500)
        self.assertEqual(parse_counter("bpftrace", "READY\n"), 0)

    def test_other_collectors_require_one_integer_snapshot(self):
        for text in ['READY\n', '{"observed":true}', '{"observed":-1}', '{"observed":1}\n{"observed":0}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_counter("libbpf", text)
        self.assertEqual(parse_counter("libbpf", 'READY\n{"observed":5500}'), 5500)


if __name__ == "__main__":
    unittest.main()
