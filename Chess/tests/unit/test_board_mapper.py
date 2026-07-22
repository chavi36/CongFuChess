import unittest
from Core.input.board_mapper import pixel_to_grid


class TestBoardMapper(unittest.TestCase):
    def test_first_cell(self):
        self.assertEqual(pixel_to_grid(50, 50), (0, 0))

    def test_second_col(self):
        self.assertEqual(pixel_to_grid(150, 50), (0, 1))

    def test_third_row(self):
        self.assertEqual(pixel_to_grid(50, 250), (2, 0))

    def test_exact_boundary(self):
        # x=100 → ceil(100/100)-1 = 0  (last pixel of col 0)
        self.assertEqual(pixel_to_grid(100, 100), (0, 0))

    def test_just_over_boundary(self):
        self.assertEqual(pixel_to_grid(101, 101), (1, 1))


if __name__ == '__main__':
    unittest.main()
