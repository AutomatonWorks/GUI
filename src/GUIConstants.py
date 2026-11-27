from __future__ import annotations

# Shared GUI sizing/typography constants for automaton_gui, mirroring the AHK
# guis/GUIConstants.ahk2 role: every value here is reused by 2+ screens, or is
# global widget chrome (theme.py's stylesheet) that affects every screen at
# once. A number used by only ONE screen lives as a constant at the top of
# that screen's own file instead - see e.g. launch.py's HEADING_FONT_SIZE.
#
# Import as a module (matches the theme/palettes.py convention) and reference
# `gc.NAME`, not `from ... import *`:
#   from automaton_gui import GUIConstants as gc
#   root.setSpacing(gc.SPACING_SCREEN)


# ---- application-wide ----
APP_FONT_POINT_SIZE = 11  # QApplication base font (theme.ThemeEngine.apply); also
                           # the point size most screens use for ordinary body text


# ---- default window size (GuiApp base; a screen overrides win_width/win_height) ----
WINDOW_DEFAULT_WIDTH = 1000
WINDOW_DEFAULT_HEIGHT = 800


# ---- shared spacing (px between children in a layout) ----
SPACING_SCREEN = 12  # top-level root layout: LaunchGUI, MacroMenu, StageSelectGUI
SPACING_ROW = 10     # a row of buttons/controls: team row, confirm buttons, editor footer


# ---- shared margins (px) ----
MARGIN_SCREEN_SIDE = 30  # left/right screen margin: LaunchGUI, MacroMenu, StageSelectGUI


# ---- shared widget sizes (px) ----
TEAM_COMBO_WIDTH = 280  # the team dropdown row: LaunchGUI, MacroMenu


# ---- shared font point sizes (px) ----
FONT_LIST = 13  # small data rows: StageSelectGUI type/stage lists, team card names


# ---- global widget chrome (theme/stylesheet.py QSS) ----
# Every value below is a literal pixel/point size baked into the app-wide QSS,
# so editing one changes that control everywhere it appears, on every screen.
CHROME_BUTTON_RADIUS = 4
CHROME_BUTTON_PADDING = "5px 14px"
CHROME_INPUT_RADIUS = 4
CHROME_INPUT_PADDING = "4px 6px"
CHROME_COMBO_DROPDOWN_WIDTH = 24
CHROME_COMBO_ARROW_SIZE = 12
CHROME_SPINNER_BUTTON_WIDTH = 16
CHROME_SPINNER_ARROW_SIZE = 10
CHROME_CHECKBOX_SIZE = 16
CHROME_CHECKBOX_RADIUS = 3
CHROME_RADIO_RADIUS = 8
CHROME_GROUPBOX_RADIUS = 6
CHROME_GROUPBOX_MARGIN_TOP = 10
CHROME_GROUPBOX_PADDING = 8
CHROME_GROUPBOX_TITLE_LEFT = 8
CHROME_GROUPBOX_TITLE_PADDING = "0 4px"
CHROME_TOOLBOX_TAB_PADDING = 6
CHROME_TAB_PADDING = "8px 18px"
CHROME_TAB_ACCENT_WIDTH = 2  # underline of the selected QTabBar tab
CHROME_MENU_FONT_SIZE = 14
CHROME_MENUBAR_ITEM_PADDING = "5px 10px"
CHROME_MENU_ITEM_PADDING = "6px 28px 6px 14px"
CHROME_MENU_SEPARATOR_HEIGHT = 1
CHROME_MENU_SEPARATOR_MARGIN = "4px 8px"
CHROME_SCROLLBAR_SIZE = 12  # width (vertical) / height (horizontal)
CHROME_SCROLLBAR_HANDLE_RADIUS = 5
CHROME_SCROLLBAR_HANDLE_MIN = 24
CHROME_ARROW_GLYPH_PX = 16  # rendered triangle PNG canvas size (_ArrowPng)
