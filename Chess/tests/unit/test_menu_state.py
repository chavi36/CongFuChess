from client.menu_state import MenuState


def test_arrow_navigation_wraps_and_selects_current_item():
    menu = MenuState(["leaderboard", "match", "create_room", "join_room"])

    assert menu.current_value() == "leaderboard"

    menu.move_down()
    assert menu.current_value() == "match"

    menu.move_up()
    assert menu.current_value() == "leaderboard"

    menu.move_down()
    menu.move_down()
    menu.move_down()
    menu.move_down()
    assert menu.current_value() == "leaderboard"
    assert menu.select() == "leaderboard"
