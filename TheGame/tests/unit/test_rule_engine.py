import unittest
from kungfu_chess.model.board import TextBoard
from kungfu_chess.rules.rule_engine import RuleEngine


def _empty(size=8):
    return [['.' for _ in range(size)] for _ in range(size)]


class TestRuleEngine(unittest.TestCase):
    def test_friendly_fire_blocked(self):
        data = _empty()
        data[4][4] = 'wR'
        data[4][7] = 'wN'
        engine = RuleEngine(TextBoard(data))
        self.assertFalse(engine.is_valid_move(4, 4, 4, 7))

    def test_capture_enemy(self):
        data = _empty()
        data[4][4] = 'wR'
        data[4][7] = 'bN'
        engine = RuleEngine(TextBoard(data))
        self.assertTrue(engine.is_valid_move(4, 4, 4, 7))

    def test_empty_source(self):
        data = _empty()
        engine = RuleEngine(TextBoard(data))
        self.assertFalse(engine.is_valid_move(4, 4, 4, 5))

    def test_distance_rook(self):
        data = _empty()
        engine = RuleEngine(TextBoard(data))
        self.assertEqual(engine.get_move_distance(0, 0, 0, 5), 5)
        self.assertEqual(engine.get_move_distance(0, 0, 3, 3), 3)


if __name__ == '__main__':
    unittest.main()
