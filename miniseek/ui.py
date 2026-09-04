#!/usr/bin/env python3
"""
MiniSeek Terminal UI Styling Engine — Purple / Violet Cyber Aesthetic.

Inspired by Hermes Agent, Claude Code, and modern terminal tooling.
Zero external dependencies, pure standard library ANSI escape sequences.
"""

import os
import sys
import shutil
from typing import List, Dict, Any, Optional, Tuple, Sequence


def _supports_color() -> bool:
    """Detects whether terminal supports ANSI color codes."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOR = _supports_color()


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Core Purple / Violet Spectrum (256-color)
    PURPLE = "\033[38;5;141m"         # Electric lavender
    BRIGHT_PURPLE = "\033[38;5;177m"  # Radiant violet
    DEEP_PURPLE = "\033[38;5;99m"     # Royal purple
    DARK_VIOLET = "\033[38;5;61m"     # Slate violet
    NEON_PURPLE = "\033[38;5;207m"    # Hot purple

    # Accents & Semantics
    CYAN = "\033[38;5;81m"
    GREEN = "\033[38;5;42m"
    BRIGHT_GREEN = "\033[38;5;48m"
    AMBER = "\033[38;5;214m"
    RED = "\033[38;5;196m"
    WHITE = "\033[97m"
    GRAY = "\033[38;5;244m"
    SLATE = "\033[38;5;239m"
    SLATE_PURPLE = "\033[38;5;60m"

    # Backgrounds for Badges & Pills
    BG_PURPLE = "\033[48;5;55m"
    BG_DARK_PURPLE = "\033[48;5;53m"
    BG_VIOLET = "\033[48;5;97m"
    BG_GREEN = "\033[48;5;28m"
    BG_AMBER = "\033[48;5;166m"
    BG_RED = "\033[48;5;160m"
    BG_SLATE = "\033[48;5;238m"


def paint(text: str, *styles: str) -> str:
    """Applies ANSI styling to text if color is supported."""
    if not USE_COLOR or not styles:
        return str(text)
    joined = "".join(styles)
    return f"{joined}{text}{Style.RESET}"


# Convenience styling helpers
def purple(text: str) -> str: return paint(text, Style.PURPLE)
def bright_purple(text: str) -> str: return paint(text, Style.BRIGHT_PURPLE)
def deep_purple(text: str) -> str: return paint(text, Style.DEEP_PURPLE)
def neon_purple(text: str) -> str: return paint(text, Style.NEON_PURPLE)
def green(text: str) -> str: return paint(text, Style.GREEN)
def bright_green(text: str) -> str: return paint(text, Style.BRIGHT_GREEN)
def amber(text: str) -> str: return paint(text, Style.AMBER)
def red(text: str) -> str: return paint(text, Style.RED)
def bright_red(text: str) -> str: return paint(text, Style.BRIGHT_RED)
def cyan(text: str) -> str: return paint(text, Style.CYAN)
def gray(text: str) -> str: return paint(text, Style.GRAY)
def dim(text: str) -> str: return paint(text, Style.DIM)
def bold(text: str) -> str: return paint(text, Style.BOLD)
def white(text: str) -> str: return paint(text, Style.WHITE)
def bright_white(text: str) -> str: return paint(text, Style.WHITE, Style.BOLD)


# Clean, non-emoji developer glyphs
GLYPH_CHECK = green("✔")
GLYPH_CROSS = red("✖")
GLYPH_WARN = amber("▲")
GLYPH_INFO = purple("ℹ")
GLYPH_DOT = purple("●")
GLYPH_ARROW = bright_purple("❯")
GLYPH_CHEVRON = gray("›")
GLYPH_DIAMOND = bright_purple("◆")
GLYPH_BLOCK = purple("■")


# ============================================================================
# Badges & Pills
# ============================================================================

def badge(text: str, bg_style: str = Style.BG_PURPLE, fg_style: str = Style.WHITE) -> str:
    """Renders a solid pill/badge."""
    if not USE_COLOR:
        return f"[{text}]"
    return f"{bg_style}{fg_style} {text} {Style.RESET}"


def badge_purple(text: str) -> str:
    return badge(text, bg_style=Style.BG_PURPLE, fg_style=Style.WHITE)


def badge_success(text: str = "SUCCESS") -> str:
    return badge(text, bg_style=Style.BG_GREEN, fg_style=Style.WHITE)


def badge_warning(text: str = "WARNING") -> str:
    return badge(text, bg_style=Style.BG_AMBER, fg_style=Style.WHITE)


def badge_error(text: str = "FAILED") -> str:
    return badge(text, bg_style=Style.BG_RED, fg_style=Style.WHITE)


def badge_info(text: str = "INFO") -> str:
    return badge(text, bg_style=Style.BG_PURPLE, fg_style=Style.WHITE)


# ============================================================================
# Status Line Reporters
# ============================================================================

def success_line(msg: str) -> None:
    print(f" {GLYPH_CHECK} {bold(msg)}")


def error_line(msg: str) -> None:
    print(f" {GLYPH_CROSS} {bright_red(bold(msg))}", file=sys.stderr)


def warn_line(msg: str) -> None:
    print(f" {GLYPH_WARN} {amber(bold(msg))}")


def info_line(msg: str) -> None:
    print(f" {GLYPH_INFO} {msg}")


def step_line(current: int, total: int, msg: str) -> None:
    idx_str = gray(f"[{current}/{total}]")
    print(f" {idx_str} {GLYPH_CHEVRON} {msg}")


def divider(width: int = 70, char: str = "─") -> None:
    print(paint(char * width, Style.SLATE_PURPLE))


def _visible_len(text: str) -> int:
    """Calculates visible character length stripping ANSI escape codes."""
    import re
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return len(ansi_escape.sub("", text))


# ============================================================================
# Sleek Hermes-Style ASCII Banner
# ============================================================================

def print_banner(subtitle: str = "Deterministic Local AI Agent Harness") -> None:
    """Renders the stylized Hermes-inspired MiniSeek ASCII header."""
    logo = [
        r"  __  __ _       _ ____            _    ",
        r" |  \/  (_)_ __ (_) ___|  ___  ___| | __",
        r" | |\/| | | '_ \| \___ \ / _ \/ _ \ |/ /",
        r" | |  | | | | | | |___) |  __/  __/   < ",
        r" |_|  |_|_|_| |_|_|____/ \___|\___|_|\_\\"
    ]

    print()
    # Print ASCII logo with vertical violet gradient
    shades = [Style.NEON_PURPLE, Style.BRIGHT_PURPLE, Style.PURPLE, Style.DEEP_PURPLE, Style.DARK_VIOLET]
    for idx, line in enumerate(logo):
        shade = shades[min(idx, len(shades) - 1)]
        print(paint(line, shade, Style.BOLD))

    # Meta status bar
    meta_pill = badge("v1.0.0", Style.BG_PURPLE, Style.WHITE)
    edge_tag = paint("Apple Silicon M1", Style.BRIGHT_PURPLE)
    mode_tag = paint("Local-First Harness", Style.GRAY)

    print()
    print(f"  {meta_pill}  {edge_tag} {gray('•')} {mode_tag} {gray('•')} {green('● Offline')}")
    print(f"  {paint(subtitle, Style.GRAY)}")
    print(paint("  " + "─" * 66, Style.SLATE_PURPLE))
    print()


# ============================================================================
# Rounded Cards & Panels
# ============================================================================

def render_card(title: str, lines: List[str], width: int = 70, border_color: str = Style.SLATE_PURPLE) -> None:
    """Renders a rounded Unicode card with purple title and dynamically sized borders."""
    max_line_len = max([_visible_len(l) for l in lines] + [0])
    actual_width = max(width, max_line_len + 6)

    title_styled = f" {bold(bright_purple(title))} "
    title_vis_len = _visible_len(title_styled)
    left_bar = "─" * 2
    right_bar_len = max(0, actual_width - 2 - len(left_bar) - title_vis_len)
    top_line = paint("╭" + left_bar, border_color) + title_styled + paint("─" * right_bar_len + "╮", border_color)

    print(top_line)
    for line in lines:
        vis_len = _visible_len(line)
        pad = max(0, actual_width - 4 - vis_len)
        border_l = paint("│", border_color)
        border_r = paint("│", border_color)
        print(f"{border_l}  {line}{' ' * pad}{border_r}")
    print(paint("╰" + "─" * (actual_width - 2) + "╯", border_color))


def render_key_values(items: List[Tuple[str, str]], width: int = 70, title: Optional[str] = None) -> None:
    """Renders aligned key-value pairs inside a styled purple-accented panel."""
    max_k_len = max(len(k) for k, _ in items) if items else 16
    lines = []
    for k, v in items:
        k_pad = k.ljust(max_k_len)
        lines.append(f"{gray(k_pad)}  {paint(':', Style.SLATE_PURPLE)}  {v}")

    if title:
        render_card(title, lines, width=width)
    else:
        for l in lines:
            print(f"  {l}")


# ============================================================================
# Tables
# ============================================================================

def render_table(
    headers: List[str],
    rows: List[List[str]],
    alignments: Optional[List[str]] = None,
    padding: int = 2
) -> None:
    """Renders a modern, bordered table with purple-tinted borders and auto-sized columns."""
    if not headers or not rows:
        return

    num_cols = len(headers)
    aligns = alignments or ["left"] * num_cols

    col_widths = [_visible_len(h) for h in headers]
    for row in rows:
        for i in range(num_cols):
            if i < len(row):
                col_widths[i] = max(col_widths[i], _visible_len(row[i]))

    border_color = Style.SLATE_PURPLE

    # Top border
    top_segs = [paint("─" * (w + padding * 2), border_color) for w in col_widths]
    print(paint("╭", border_color) + paint("┬", border_color).join(top_segs) + paint("╮", border_color))

    # Header row
    hdr_cells = []
    for i, h in enumerate(headers):
        pad_str = " " * padding
        w = col_widths[i]
        val_w = _visible_len(h)
        diff = w - val_w
        align = aligns[i]
        if align == "right":
            cell = f"{pad_str}{' ' * diff}{bold(white(h))}{pad_str}"
        elif align == "center":
            left_diff = diff // 2
            right_diff = diff - left_diff
            cell = f"{pad_str}{' ' * left_diff}{bold(white(h))}{' ' * right_diff}{pad_str}"
        else:
            cell = f"{pad_str}{bold(white(h))}{' ' * diff}{pad_str}"
        hdr_cells.append(cell)

    print(paint("│", border_color) + paint("│", border_color).join(hdr_cells) + paint("│", border_color))

    # Divider
    div_segs = [paint("─" * (w + padding * 2), border_color) for w in col_widths]
    print(paint("├", border_color) + paint("┼", border_color).join(div_segs) + paint("┤", border_color))

    # Data rows
    for row in rows:
        row_cells = []
        for i in range(num_cols):
            val = row[i] if i < len(row) else ""
            pad_str = " " * padding
            w = col_widths[i]
            val_w = _visible_len(val)
            diff = max(0, w - val_w)
            align = aligns[i]
            if align == "right":
                cell = f"{pad_str}{' ' * diff}{val}{pad_str}"
            elif align == "center":
                left_diff = diff // 2
                right_diff = diff - left_diff
                cell = f"{pad_str}{' ' * left_diff}{val}{' ' * right_diff}{pad_str}"
            else:
                cell = f"{pad_str}{val}{' ' * diff}{pad_str}"
            row_cells.append(cell)
        print(paint("│", border_color) + paint("│", border_color).join(row_cells) + paint("│", border_color))

    # Bottom border
    bot_segs = [paint("─" * (w + padding * 2), border_color) for w in col_widths]
    print(paint("╰", border_color) + paint("┴", border_color).join(bot_segs) + paint("╯", border_color))


# ============================================================================
# Progress & Distribution Bars
# ============================================================================

def render_progress_bar(current: int, total: int, width: int = 20, label: str = "") -> str:
    """Returns a styled inline progress bar: [████████░░░░] 60% (3/5)"""
    if total <= 0:
        return ""
    pct = min(1.0, max(0.0, current / total))
    filled_len = int(round(width * pct))
    empty_len = width - filled_len

    bar = (
        bright_purple("█" * filled_len) +
        paint("░" * empty_len, Style.SLATE_PURPLE)
    )
    pct_text = bold(f"{int(pct * 100):>3}%")
    counts = gray(f"({current}/{total})")
    extra = f" {label}" if label else ""
    return f"[{bar}] {pct_text} {counts}{extra}"
