import unittest
from helper.year_operation import categorize_by_age

class TestCategorizeByAge(unittest.TestCase):
    def setUp(self):
        print("\nStarting a new test case...")
    def tearDown(self):
        print("test case finished \n")
    def test_child(self):
        self.assertEqual(categorize_by_age(5), "Child")
    def test_child_negative(self):
        self.assertNotIn(categorize_by_age(5), ["Adolescent", "Adult", "Golden age", "Invalid age: 5"])
    def test_adolecent(self):
        self.assertEqual(categorize_by_age(15), "Adolescent")
    def test_adolecent_two(self):
        self.assertEqual(categorize_by_age(60), "Adult")
    def test_adult(self):
        self.assertEqual(categorize_by_age(30), "Adult")
    def test_golden_age(self):
        self.assertEqual(categorize_by_age(70), "Golden age")
    def test_negative_age(self):
        self.assertEqual(categorize_by_age(-1), "Invalid age: -1")
    def test_too_old(self):
        self.assertEqual(categorize_by_age(155), "Invalid age: 155")
    def test_too_old_negative(self):
        self.assertNotIn(categorize_by_age(155), ["Child", "Adolescent", "Adult", "Golden age"])

if __name__ == '__main__':
    unittest.main(verbosity=2)