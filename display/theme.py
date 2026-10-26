from typing import Dict, Tuple
import pygame

class Colors:
    # ==========================================
    # 1. BẢNG MÀU CHỦ ĐẠO (BD-1 BRAND PALETTE)
    # ==========================================
    FOREST_GREEN = (24, 61, 48)     # #183D30 - Màu chủ đạo: xanh rừng sâu
    PINE_GREEN   = (40, 87, 67)     # #285743 - Xanh thông: nút chính & điểm nhấn tương tác
    SAGE_MUTED   = (170, 185, 173)  # #AAB9AD - Xanh xám dịu: icon phụ & trạng thái nhẹ
    MIST_GRAY    = (221, 226, 222)  # #DDE2DE - Xám sương: nền phụ & viền phân vùng
    SNOW_WHITE   = (245, 247, 244)  # #F5F7F4 - Trắng sương: nền sáng chính toàn trang

    # ==========================================
    # 2. MÀU CƠ BẢN & PHỤ TRỢ
    # ==========================================
    COLOR_WHITE      = (255, 255, 255)
    COLOR_DANGER     = (215, 60, 60)
    PINE_GREEN_LIGHT = (232, 240, 235)

    # ==========================================
    # 3. MÀU NỀN & PHÂN VÙNG (BACKGROUNDS & PANELS)
    # ==========================================
    PAGE_BG          = SNOW_WHITE               # Nền chính toàn màn hình
    BG_PAGE          = SNOW_WHITE               # Alias cho PAGE_BG
    CARD_BG          = (255, 255, 255)          # Nền thẻ trắng chính
    CARD_BG_MUTED    = (235, 239, 236)          # Nền phụ xám xanh nhẹ cho card / item
    CARD_BORDER      = MIST_GRAY                # Viền card / đường phân cách
    TERMINAL_BG      = (18, 38, 30)             # Nền console log xanh rừng sâu tối đậm
    TAB_BG           = MIST_GRAY                # Nền phân vùng chuyển tab
    CONNECTED_BG     = PINE_GREEN               # Nền badge / nút trạng thái kết nối
    OVERLAY_BG       = (24, 61, 48)             # Lớp phủ mờ modal

    # ==========================================
    # 4. MÀU CHỮ & TYPOGRAPHY
    # ==========================================
    TEXT_MAIN        = FOREST_GREEN             # Chữ tiêu đề & nhãn chính
    TEXT_DARK        = FOREST_GREEN             # Alias cho TEXT_MAIN
    TEXT_MUTED       = (95, 115, 105)           # Chữ phụ thanh nhã, dễ đọc
    TEXT_LIGHT       = SAGE_MUTED               # Chữ làm mờ nhẹ
    TEXT_FOOTER      = SAGE_MUTED               # Chữ chân trang

    # ==========================================
    # 5. NÚT BẤM & TRẠNG THÁI (BUTTONS & STATES)
    # ==========================================
    BTN_PRIMARY         = PINE_GREEN            # Nút bấm chính
    BTN_PRIMARY_HOVER   = FOREST_GREEN          # Nút bấm chính khi hover/nhấn
    BTN_SECONDARY       = MIST_GRAY             # Nút bấm phụ
    BTN_SECONDARY_HOVER = (205, 212, 207)       # Nút bấm phụ khi hover
    BTN_BG              = PINE_GREEN            # Alias nút bấm chính
    BTN_HOVER           = FOREST_GREEN          # Alias nút bấm hover
    SUCCESS_COLOR       = PINE_GREEN            # Màu thông báo thành công
    ERROR_COLOR         = COLOR_DANGER          # Màu thông báo lỗi
    GREEN_STATUS        = PINE_GREEN            # Chấm trạng thái hoạt động tốt
    BORDER_RADIO        = SAGE_MUTED            # Viền nút chọn radio
    BORDER_ACTIVE       = PINE_GREEN            # Viền khi được chọn active

    # ==========================================
    # 6. BÀN PHÍM SỐ & MÃ PIN (KEYPAD & PIN)
    # ==========================================
    KEY_BG              = (255, 255, 255)       # Nền phím số
    KEY_BG_HOVER        = (235, 239, 236)       # Nền phím số khi hover
    KEY_BORDER          = MIST_GRAY             # Viền phím số

    # ==========================================
    # 7. Ô NHẬP LIỆU (INPUT FIELDS)
    # ==========================================
    INPUT_BG            = (255, 255, 255)       # Nền ô nhập liệu
    INPUT_BORDER        = MIST_GRAY             # Viền ô nhập liệu
    INPUT_BORDER_FOCUS  = PINE_GREEN            # Viền ô nhập liệu khi chọn (focus)
    INPUT_FOCUS         = PINE_GREEN            # Alias INPUT_BORDER_FOCUS
    INPUT_PLACEHOLDER   = SAGE_MUTED            # Màu chữ placeholder

    # ==========================================
    # 8. HUY HIỆU & ICON (BADGES & ICONS)
    # ==========================================
    BADGE_BG_READY      = (230, 240, 235)       # Nền huy hiệu sẵn sàng
    BADGE_TEXT_READY    = PINE_GREEN            # Chữ huy hiệu sẵn sàng
    GREEN_BG            = (232, 240, 235)       # Nền icon xanh nhẹ
    GREEN_BORDER        = SAGE_MUTED            # Viền icon
    GREEN_TEXT          = PINE_GREEN            # Chữ icon
    GREEN_CHECK         = PINE_GREEN            # Dấu tích xanh
    GREEN_ICON          = PINE_GREEN            # Biểu tượng xanh

    # ==========================================
    # 9. KHUÔN MẶT BIỂU CẢM (ROBOT FACE)
    # ==========================================
    COLOR_BG            = SNOW_WHITE            # Nền khuôn mặt biểu cảm
    COLOR_INK           = FOREST_GREEN          # Nét vẽ biểu cảm mắt, miệng BD-1
    COLOR_TEETH         = COLOR_WHITE           # Răng biểu cảm cười

    # ==========================================
    # 10. ASSISTIVE TOUCH (NÚT NỔI & MENU ĐIỀU KHIỂN)
    # ==========================================
    MENU_SLATE          = PINE_GREEN
    MENU_WARM_BG        = SNOW_WHITE


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
