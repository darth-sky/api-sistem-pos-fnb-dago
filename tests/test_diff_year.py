import unittest
from unittest.mock import patch
import datetime

# Assume diff_year is defined in a module called helper.year_operation
from helper.year_operation import diff_year

class TestDiffYear(unittest.TestCase):
    @patch('datetime.datetime')
    def test_diff_year(self, mock_datetime):
        # Mock the current date
        mock_datetime.now.return_value = datetime.datetime(2024, 1, 1)
        mock_datetime.now.return_value.year = 2024
        mock_datetime.side_effect = lambda *args, **kwargs: datetime.datetime(*args, **kwargs)

        # Test cases
        self.assertEqual(diff_year(2020), 4)  # 2024 - 2020 = 4
        self.assertEqual(diff_year(2000), 24)  # 2024 - 2000 = 24
        self.assertEqual(diff_year(2024), 0)  # 2024 - 2024 = 0
        self.assertNotIn(diff_year(2100), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        # Edge case
        self.assertEqual(diff_year(2100), -76)  # 2024 - 2100 = -76

if __name__ == '__main__':
    unittest.main(verbosity=2)
