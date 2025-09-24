import unittest
from helper.testCase import selection_sort  # Sesuaikan path modul Anda

class TestSelectionSort(unittest.TestCase):
    def setUp(self):
        print("\nStarting a new test case...")

    def tearDown(self):
        print("Test case finished\n")

    def test_empty_list(self):
        self.assertEqual(selection_sort([]), [])

    def test_single_element(self):
        self.assertEqual(selection_sort([42]), [42])

    def test_sorted_list(self):
        self.assertEqual(selection_sort([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])

    def test_reverse_sorted_list(self):
        self.assertEqual(selection_sort([5, 4, 3, 2, 1]), [1, 2, 3, 4, 5])

    def test_unsorted_list(self):
        self.assertEqual(selection_sort([64, 34, 25, 12, 22, 11, 90]), [11, 12, 22, 25, 34, 64, 90])

    def test_duplicates(self):
        self.assertEqual(selection_sort([3, 1, 2, 3, 1, 2]), [1, 1, 2, 2, 3, 3])

    def test_negative_numbers(self):
        self.assertEqual(selection_sort([-1, -3, -2, 0, 2, 1]), [-3, -2, -1, 0, 1, 2])
    
    def test_float_number(self):
        self.assertEqual(selection_sort([1.1, 3.3, 2.2]), [1.1, 2.2, 3.3])

    def test_large_numbers(self):
        self.assertEqual(selection_sort([1_000_000, 500_000, 1_500_000]), [500_000, 1_000_000, 1_500_000])

    def test_all_identical_elements(self):
        self.assertEqual(selection_sort([5, 5, 5, 5, 5]), [5, 5, 5, 5, 5])

    def test_floats_and_integers(self):
        self.assertEqual(selection_sort([1.2, 3, 2.5, 0.5]), [0.5, 1.2, 2.5, 3])

    def test_single_negative_element(self):
        self.assertEqual(selection_sort([-10]), [-10])

    def test_mixed_sign_numbers(self):
        self.assertEqual(selection_sort([3, -2, 0, 1, -1]), [-2, -1, 0, 1, 3])

    def test_large_dataset(self):
        self.assertEqual(selection_sort(list(range(1000, 0, -1))), list(range(1, 1001)))

    def test_all_alphabets(self):
        self.assertEqual(selection_sort(['z', 'b', 'a', 'd']), ['a', 'b', 'd', 'z'])

    def test_mixed_alphabets_and_numbers(self):
        with self.assertRaises(TypeError):
            selection_sort([1, 'b', 3, 'a'])

    def test_reverse_sorted_list(self):
        self.assertEqual(selection_sort([9, 8, 7, 6, 5]), [5, 6, 7, 8, 9])

    def test_empty_list(self):
        self.assertEqual(selection_sort([]), [])

    def test_single_element(self):
        self.assertEqual(selection_sort([1]), [1])

    def test_already_sorted_list(self):
        self.assertEqual(selection_sort([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])

    def test_duplicate_elements1(self):
        self.assertEqual(selection_sort([5, 1, 5, 3, 2]), [1, 2, 3, 5, 5])

    def test_duplicate_elements(self):
        self.assertEqual(selection_sort([4, 2, 2, 8, 3, 3, 1]) == [1, 2, 2, 3, 3, 4, 8])
if __name__ == '__main__':
    unittest.main(verbosity=2)
