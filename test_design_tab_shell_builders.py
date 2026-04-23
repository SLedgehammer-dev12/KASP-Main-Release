from kasp.ui.design_tab_shell_builders import (
    get_design_left_scroll_width_range,
    get_design_tab_margins,
    get_design_tab_spacing,
)


def test_design_tab_shell_layout_defaults_remain_stable():
    assert get_design_tab_margins() == (4, 4, 4, 4)
    assert get_design_tab_spacing() == 6
    assert get_design_left_scroll_width_range() == (360, 520)
