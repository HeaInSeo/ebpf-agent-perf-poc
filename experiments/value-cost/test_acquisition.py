import unittest
from run import parse_maps
from analyze import rank

class EvidenceTests(unittest.TestCase):
    def test_exact_end_map_format(self):
        m=parse_maps("READY\n@calls[0]: 10\n@calls[1]: 8\n@bytes[0]: 4096\n@bytes[1]: 4096\n")
        self.assertEqual(m["calls"],{"0":10,"1":8})
        self.assertEqual(m["bytes"],{"0":4096,"1":4096})
        self.assertEqual(m["errors"],{"0":0,"1":0})
    def test_abstain_and_clear_ranking(self):
        self.assertEqual(rank([1.01]*12)["choice"],"ABSTAIN")
        self.assertEqual(rank([.90]*12)["choice"],"B")
        self.assertEqual(rank([1.10]*12)["choice"],"A")

if __name__=="__main__":unittest.main()
