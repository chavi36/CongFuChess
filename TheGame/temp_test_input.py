import sys, subprocess

cases = [
    ('jump_lands_same_square', 'Board:\n. . .\n. wK .\n. . .\nCommands:\njump 150 150\nwait 1000\nprint board\n'),
    ('airborne_piece_captures_arriving_enemy', 'Board:\n. . .\nwK . bR\n. . .\nCommands:\njump 50 150\nclick 250 150\nclick 50 150\nwait 1000\nprint board\n'),
    ('jump_too_late_does_not_save_piece', 'Board:\n. . .\nwK . bR\n. . .\nCommands:\nclick 250 150\nclick 50 150\nwait 1000\njump 50 150\nprint board\n'),
    ('enemy_arrives_after_landing_captures_normally', 'Board:\n. . . .\nwK . . bR\n. . . .\nCommands:\njump 50 150\nwait 1000\nclick 350 150\nclick 50 150\nwait 3000\nprint board\n'),
    ('cannot_jump_while_moving', 'Board:\nwR . .\nCommands:\nclick 50 50\nclick 250 50\nwait 500\njump 50 50\nwait 1500\nprint board\n'),
    ('airborne_capture_only_enemy', 'Board:\n. . .\nwK . wR\n. . .\nCommands:\njump 50 150\nclick 250 150\nclick 50 150\nwait 1000\nprint board\n'),
]
for name, inp in cases:
    print('===', name)
    p = subprocess.Popen([sys.executable, 'main.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate(inp)
    print('OUT:')
    print(out)
    print('ERR:')
    print(err)
