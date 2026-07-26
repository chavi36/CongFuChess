from client.client import _get_menu_option_index_from_click


def test_click_returns_matching_menu_option_index():
    item_x = 100
    item_w = 320
    start_y = 170
    item_h = 70

    assert _get_menu_option_index_from_click(120, 180, item_x, item_w, start_y, item_h, 4) == 0
    assert _get_menu_option_index_from_click(120, 250, item_x, item_w, start_y, item_h, 4) == 1
    assert _get_menu_option_index_from_click(120, 390, item_x, item_w, start_y, item_h, 4) == 3
    assert _get_menu_option_index_from_click(50, 180, item_x, item_w, start_y, item_h, 4) is None
    assert _get_menu_option_index_from_click(120, 500, item_x, item_w, start_y, item_h, 4) is None
