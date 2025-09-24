import unittest
from helper.year_operation import check_age_book

class TestCheckAgeBook(unittest.TestCase):
    def setUp(self):
        print("\nStarting a new test case...")
    def tearDown(self):
        print("test case finished \n")
    def test_new(self):
        self.assertEqual(check_age_book(5), "New")
    def test_new_negative(self):
        self.assertNotIn(check_age_book(5), ["Mid Year", "Old", "Ancient", "Invalid age: 5"])
    def test_mid(self):
        self.assertEqual(check_age_book(15), "Mid Year")
    def test_old(self):
        self.assertEqual(check_age_book(60), "Old")
    def test_ancient(self):
        self.assertEqual(check_age_book(101), "Ancient")
    def test_negative(self):
        self.assertEqual(check_age_book(-1), "Invalid age: -1")


if __name__ == '__main__':
    unittest.main(verbosity=2)