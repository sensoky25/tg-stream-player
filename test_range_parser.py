import unittest
from server import parse_range_header

class TestRangeParser(unittest.TestCase):
    def test_full_range(self):
        start, end, is_range = parse_range_header("bytes=0-", 1000)
        self.assertEqual((start, end, is_range), (0, 999, True))

    def test_specific_range(self):
        start, end, is_range = parse_range_header("bytes=100-500", 1000)
        self.assertEqual((start, end, is_range), (100, 500, True))

    def test_suffix_range(self):
        start, end, is_range = parse_range_header("bytes=-200", 1000)
        self.assertEqual((start, end, is_range), (800, 999, True))

    def test_no_range(self):
        start, end, is_range = parse_range_header(None, 1000)
        self.assertEqual((start, end, is_range), (0, 999, False))

    def test_invalid_range_start_greater_than_end(self):
        start, end, is_range = parse_range_header("bytes=500-100", 1000)
        self.assertIsNone(start)

    def test_range_exceeding_size(self):
        start, end, is_range = parse_range_header("bytes=1000-2000", 1000)
        self.assertIsNone(start)

if __name__ == "__main__":
    unittest.main()
