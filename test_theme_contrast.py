"""
Tests to programmatically verify contrast ratios in theme profiles (light, dark, engineering).
Uses WCAG 2.0 relative luminance and contrast ratio formulas to safeguard visual accessibility.
"""

import pytest
from kasp.ui.theme_manager import ThemeManager

def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    """Parse #RRGGBB or #RGB into (r, g, b) integer tuples."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        raise ValueError(f"Invalid hex color format: {hex_str}")
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)

def calculate_relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance using WCAG 2.0 formula."""
    rs = r / 255.0
    gs = g / 255.0
    bs = b / 255.0
    
    r_val = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
    g_val = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
    b_val = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * r_val + 0.7152 * g_val + 0.0722 * b_val

def get_contrast_ratio(color_a: str, color_b: str) -> float:
    """Calculate contrast ratio between two hex colors."""
    r1, g1, b1 = parse_hex_color(color_a)
    r2, g2, b2 = parse_hex_color(color_b)
    
    l1 = calculate_relative_luminance(r1, g1, b1)
    l2 = calculate_relative_luminance(r2, g2, b2)
    
    lighter = max(l1, l2)
    darker = min(l1, l2)
    
    return (lighter + 0.05) / (darker + 0.05)

def test_theme_contrast_ratios():
    """Verify that essential text-to-background and alert contrast ratios meet WCAG 2.0 standards."""
    min_contrast_normal_text = 4.5
    min_contrast_secondary_text = 3.0
    min_contrast_alert_text = 4.0
    
    failures = []
    
    for theme_name, colors in ThemeManager.THEMES.items():
        # 1. Main background and text
        bg = colors["background"]
        text = colors["text"]
        text_sec = colors["text_secondary"]
        surface = colors["surface"]
        
        # Test background vs primary text
        contrast_main = get_contrast_ratio(bg, text)
        if contrast_main < min_contrast_normal_text:
            failures.append(
                f"Theme '{theme_name}': background ({bg}) vs text ({text}) contrast ratio "
                f"is {contrast_main:.2f}, below target {min_contrast_normal_text}"
            )
            
        # Test surface vs primary text
        contrast_surf = get_contrast_ratio(surface, text)
        if contrast_surf < min_contrast_normal_text:
            failures.append(
                f"Theme '{theme_name}': surface ({surface}) vs text ({text}) contrast ratio "
                f"is {contrast_surf:.2f}, below target {min_contrast_normal_text}"
            )
            
        # Test background vs secondary text
        contrast_sec = get_contrast_ratio(bg, text_sec)
        if contrast_sec < min_contrast_secondary_text:
            failures.append(
                f"Theme '{theme_name}': background ({bg}) vs text_secondary ({text_sec}) contrast ratio "
                f"is {contrast_sec:.2f}, below target {min_contrast_secondary_text}"
            )

        # 2. Alert/Status Colors (Success, Danger, Warning states)
        # Success Contrast
        sc_bg = colors["success_bg"]
        sc_text = colors["success_text"]
        contrast_success = get_contrast_ratio(sc_bg, sc_text)
        if contrast_success < min_contrast_alert_text:
            failures.append(
                f"Theme '{theme_name}': success_bg ({sc_bg}) vs success_text ({sc_text}) contrast ratio "
                f"is {contrast_success:.2f}, below target {min_contrast_alert_text}"
            )

        # Danger Contrast
        dg_bg = colors["danger_bg"]
        dg_text = colors["danger_text"]
        contrast_danger = get_contrast_ratio(dg_bg, dg_text)
        if contrast_danger < min_contrast_alert_text:
            failures.append(
                f"Theme '{theme_name}': danger_bg ({dg_bg}) vs danger_text ({dg_text}) contrast ratio "
                f"is {contrast_danger:.2f}, below target {min_contrast_alert_text}"
            )

        # Warning Contrast
        wn_bg = colors["warning_bg"]
        wn_text = colors["warning_text"]
        contrast_warning = get_contrast_ratio(wn_bg, wn_text)
        if contrast_warning < min_contrast_alert_text:
            failures.append(
                f"Theme '{theme_name}': warning_bg ({wn_bg}) vs warning_text ({wn_text}) contrast ratio "
                f"is {contrast_warning:.2f}, below target {min_contrast_alert_text}"
            )
            
    assert not failures, "Theme contrast failures detected:\n" + "\n".join(failures)
