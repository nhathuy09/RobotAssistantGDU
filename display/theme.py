from typing import Dict, Tuple
import pygame

class Colors:
    COLOR_747A80 = (116, 122, 128)  # Muted Slate Grey
    COLOR_FFFEFB = (255, 254, 251)  # Warm White
    COLOR_2B303A = (43, 48, 58)     # Dark Charcoal
    COLOR_E2E1DA = (226, 225, 218)  # Light Warm Border
    COLOR_62798C = (98, 121, 140)   # Slate Blue Accent
    COLOR_C8CCC8 = (200, 204, 200)  # Soft Border / Radio
    COLOR_F0F0EB = (240, 240, 235)  # Page Background
    COLOR_7C8D7C = (124, 141, 124)  # Sage Green Icon
    COLOR_6B8675 = (107, 134, 117)  # Active Sage Green
    COLOR_A7B7AC = (167, 183, 172)  # Light Sage Border
    COLOR_DFE7E0 = (223, 231, 224)  # Mint Sage Background
    COLOR_DANGER = (220, 38, 38)
    
    COLOR_BG = (205, 214, 224)
    COLOR_INK = (24, 26, 32)
    COLOR_TEETH = (255, 255, 255)

    BG_PAGE = COLOR_F0F0EB
    CARD_BG = COLOR_FFFEFB
    CARD_BORDER = COLOR_E2E1DA
    TEXT_DARK = COLOR_2B303A
    TEXT_MUTED = COLOR_747A80
    TEXT_LABEL = COLOR_2B303A
    BTN_PRIMARY = COLOR_62798C
    BTN_PRIMARY_HOVER = (82, 103, 120)
    BORDER_RADIO = COLOR_C8CCC8
    GREEN_BG = COLOR_DFE7E0
    GREEN_BORDER = COLOR_A7B7AC
    GREEN_TEXT = COLOR_6B8675
    GREEN_CHECK = COLOR_6B8675
    GREEN_ICON = COLOR_7C8D7C
    INPUT_BG = COLOR_F0F0EB
    INPUT_BORDER = COLOR_E2E1DA
    INPUT_BORDER_FOCUS = COLOR_62798C
        # Assistive Touch
    MENU_SLATE = COLOR_62798C
    MENU_WARM_BG = COLOR_F0F0EB
    COLOR_WHITE = COLOR_TEETH
class Theme:
    WIDTH = 800
    HEIGHT = 480
    FPS = 30
    def __init__(self):
        self._font_cache: Dict[Tuple[int, bool], pygame.font.Font] = {}
        self.init_fonts()
    def get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key in self._font_cache:
            return self._font_cache[key]
        font = None
        for f_name in ["Segoe UI", "Arial", "Times New Roman"]:
            try:
                font = pygame.font.SysFont(f_name, size, bold=bold)
                if font:
                    break
            except Exception:
                continue
        if not font:
            font = pygame.font.Font(None, size)
        self._font_cache[key] = font
        return font
    def init_fonts(self):
        self.font_h1 = self.get_font(22, bold=True)
        self.font_h2 = self.get_font(18, bold=True)
        self.font_title = self.get_font(15, bold=True)
        self.font_body = self.get_font(14)
        self.font_body_bold = self.get_font(14, bold=True)
        self.font_small = self.get_font(12)
        self.font_small_bold = self.get_font(12, bold=True)
        self.font_pin = self.get_font(28, bold=True)
