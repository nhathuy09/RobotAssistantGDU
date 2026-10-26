import math
import random
import time
import pygame
from typing import List, Optional, Tuple, Dict
from display.screens.base_screen import BaseScreen
from display.theme import Colors


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def get_bezier_points(p0, p1, p2, steps: int = 20) -> List[Tuple[float, float]]:
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        points.append((x, y))
    return points


def get_cubic_bezier_points(p0, p1, p2, p3, steps: int = 36) -> List[Tuple[float, float]]:
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


class AnimeRobotFace:
    

    VALID_STATES = ["IDLE", "ACTIVE", "LISTENING", "THINKING", "SPEAKING", "ACTING", "WAKEWORD", "SLEEP", "STANDBY"]

    def __init__(
        self,
        surface: pygame.Surface,
        cx: int = 400,
        cy: int = 225,
        scale: float = 2.1,
        ink_color: Optional[Tuple[int, int, int]] = None,
        bg_color: Optional[Tuple[int, int, int]] = None,
        teeth_color: Optional[Tuple[int, int, int]] = None,
    ):
        self.surface = surface
        self.cx = cx
        self.cy = cy
        self.scale = scale
        self.ink_color = ink_color or Colors.COLOR_INK
        self.bg_color = bg_color or Colors.COLOR_BG
        self.teeth_color = teeth_color or Colors.COLOR_TEETH

        self.current_state = "IDLE"
        self.state_enter_time = time.monotonic() - 10.0

        self.eye_w = 46.0
        self.eye_h = 78.0
        self.eye_spacing = 150.0
        self.blink_progress = 0.0
        self.is_blinking = False
        self.next_blink = time.monotonic() + 3.0

        self.eyebrow_lift = 0.0
        self.mouth_open = 0.0
        self.mouth_phase = 0.0
        self.breath_phase = 0.0
        self.sleep_progress = 1.0

    def s(self, value: float) -> float:
        return value * self.scale

    def set_colors(
        self,
        ink_color: Optional[Tuple[int, int, int]] = None,
        bg_color: Optional[Tuple[int, int, int]] = None,
        teeth_color: Optional[Tuple[int, int, int]] = None,
    ):
        if ink_color is not None:
            self.ink_color = ink_color
        if bg_color is not None:
            self.bg_color = bg_color
        if teeth_color is not None:
            self.teeth_color = teeth_color

    def trigger_blink(self):
        """Kích hoạt chớp mắt tức thì để xem trước hoạt ảnh."""
        self.is_blinking = True
        self.blink_progress = 0.0

    def set_state(self, state: str):
        state = state.upper()
        if state in self.VALID_STATES and state != self.current_state:
            self.current_state = state
            self.state_enter_time = time.monotonic()
            if state in ["ACTIVE", "LISTENING", "SPEAKING", "THINKING", "ACTING"]:
                self.sleep_progress = 0.0

    def update(self):
        now = time.monotonic()

        # Tự động ngủ khi IDLE sau 5s hoặc các trạng thái ngủ
        if self.current_state in ["WAKEWORD", "SLEEP", "STANDBY"]:
            target_sleep = 1.0
        elif self.current_state in ["ACTIVE", "LISTENING", "SPEAKING", "THINKING", "ACTING"]:
            target_sleep = 0.0
        elif self.current_state == "IDLE":
            target_sleep = 1.0 if (now - self.state_enter_time) > 5.0 else 0.0
        else:
            target_sleep = 0.0

        self.sleep_progress = lerp(self.sleep_progress, target_sleep, 0.12)

        # Chớp mắt khi thức
        if self.sleep_progress < 0.3:
            if now >= self.next_blink and not self.is_blinking:
                self.is_blinking = True
                self.blink_progress = 0.0
            if self.is_blinking:
                self.blink_progress += 0.16
                if self.blink_progress >= 1.0:
                    self.is_blinking = False
                    self.blink_progress = 0.0
                    self.next_blink = now + random.uniform(2.5, 5.0)
        else:
            self.is_blinking = False
            self.blink_progress = 0.0
            self.next_blink = now + random.uniform(2.5, 4.0)

        # Nhịp thở
        breath_speed = 0.025 if self.sleep_progress > 0.5 else 0.035
        self.breath_phase += breath_speed

        # Cử động lông mày và miệng
        target_lift = 0.0
        target_open = 0.0
        if self.current_state in ["WAKEWORD", "SLEEP", "STANDBY"]:
            target_lift = 4.0
        elif self.current_state == "LISTENING":
            target_lift = -12.0
        elif self.current_state == "THINKING":
            target_lift = 8.0
        elif self.current_state == "SPEAKING":
            self.mouth_phase += 0.28
            target_open = (math.sin(self.mouth_phase) + 1.0) * 8.0
            target_lift = math.sin(self.mouth_phase * 0.5) * 4.0
        elif self.current_state == "ACTING":
            target_lift = -6.0

        self.eyebrow_lift = lerp(self.eyebrow_lift, target_lift, 0.2)
        self.mouth_open = lerp(self.mouth_open, target_open, 0.3)

    def draw_eyebrows(self, center_y: float):
        brow_y = center_y - self.s(68) + self.s(self.eyebrow_lift)
        line_w = max(1, int(self.s(8)))
        cap_r = max(1, int(self.s(4)))

        # Lông mày trái
        p0_l = (self.cx - self.s(110), brow_y + self.s(10))
        p1_l = (self.cx - self.s(75), brow_y - self.s(18))
        p2_l = (self.cx - self.s(38), brow_y + self.s(2))
        pts_left = get_bezier_points(p0_l, p1_l, p2_l)
        pygame.draw.lines(self.surface, self.ink_color, False, pts_left, line_w)
        pygame.draw.circle(self.surface, self.ink_color, (int(p0_l[0]), int(p0_l[1])), cap_r)
        pygame.draw.circle(self.surface, self.ink_color, (int(p2_l[0]), int(p2_l[1])), cap_r)

        # Lông mày phải
        p0_r = (self.cx + self.s(38), brow_y + self.s(2))
        p1_r = (self.cx + self.s(75), brow_y - self.s(18))
        p2_r = (self.cx + self.s(110), brow_y + self.s(10))
        pts_right = get_bezier_points(p0_r, p1_r, p2_r)
        pygame.draw.lines(self.surface, self.ink_color, False, pts_right, line_w)
        pygame.draw.circle(self.surface, self.ink_color, (int(p0_r[0]), int(p0_r[1])), cap_r)
        pygame.draw.circle(self.surface, self.ink_color, (int(p2_r[0]), int(p2_r[1])), cap_r)

    def draw_eyes(self, center_y: float):
        eye_w = self.s(self.eye_w)
        spacing = self.s(self.eye_spacing)
        lx = self.cx - spacing / 2
        rx = self.cx + spacing / 2

        if self.sleep_progress > 0.35:
            # Mắt nhắm hình cung cong ︶ ︶
            t = min(1.0, (self.sleep_progress - 0.35) / 0.65)
            arc_w = eye_w * 1.15
            arc_depth = self.s(13.0) * t
            base_y = center_y + self.s(4.0)
            line_w = max(1, int(self.s(8.0)))
            cap_r = max(1, int(self.s(4.0)))

            p0_el = (lx - arc_w / 2, base_y - self.s(4.0) * t)
            p1_el = (lx, base_y + arc_depth)
            p2_el = (lx + arc_w / 2, base_y - self.s(4.0) * t)
            pts_el = get_bezier_points(p0_el, p1_el, p2_el, 20)
            pygame.draw.lines(self.surface, self.ink_color, False, pts_el, line_w)
            pygame.draw.circle(self.surface, self.ink_color, (int(p0_el[0]), int(p0_el[1])), cap_r)
            pygame.draw.circle(self.surface, self.ink_color, (int(p2_el[0]), int(p2_el[1])), cap_r)

            p0_er = (rx - arc_w / 2, base_y - self.s(4.0) * t)
            p1_er = (rx, base_y + arc_depth)
            p2_er = (rx + arc_w / 2, base_y - self.s(4.0) * t)
            pts_er = get_bezier_points(p0_er, p1_er, p2_er, 20)
            pygame.draw.lines(self.surface, self.ink_color, False, pts_er, line_w)
            pygame.draw.circle(self.surface, self.ink_color, (int(p0_er[0]), int(p0_er[1])), cap_r)
            pygame.draw.circle(self.surface, self.ink_color, (int(p2_er[0]), int(p2_er[1])), cap_r)
        else:
            # Mắt mở hình chữ nhật bo tròn
            h = self.s(self.eye_h) * (1.0 - self.sleep_progress * 1.6)
            if self.is_blinking:
                factor = abs(self.blink_progress - 0.5) * 2.0
                h = max(self.s(6), self.s(self.eye_h) * factor)
            h = max(self.s(6), h)

            radius = max(1, int(eye_w / 2))
            rect_l = pygame.Rect(int(lx - eye_w / 2), int(center_y - h / 2), int(eye_w), int(h))
            rect_r = pygame.Rect(int(rx - eye_w / 2), int(center_y - h / 2), int(eye_w), int(h))
            pygame.draw.rect(self.surface, self.ink_color, rect_l, border_radius=radius)
            pygame.draw.rect(self.surface, self.ink_color, rect_r, border_radius=radius)

    def draw_blush(self, center_y: float):
        blush_y = center_y + self.s(46)
        dy = self.s(20)
        dx = self.s(7)
        line_w = max(1, int(self.s(6)))
        lx = self.cx - self.s(120)
        rx = self.cx + self.s(120)

        pygame.draw.line(self.surface, self.ink_color, (lx - self.s(12), blush_y - dy / 2), (lx - self.s(12) + dx, blush_y + dy / 2), line_w)
        pygame.draw.line(self.surface, self.ink_color, (lx + self.s(4), blush_y - dy / 2), (lx + self.s(4) + dx, blush_y + dy / 2), line_w)
        pygame.draw.line(self.surface, self.ink_color, (rx - self.s(4), blush_y - dy / 2), (rx - self.s(4) + dx, blush_y + dy / 2), line_w)
        pygame.draw.line(self.surface, self.ink_color, (rx + self.s(12), blush_y - dy / 2), (rx + self.s(12) + dx, blush_y + dy / 2), line_w)

    def draw_mouth(self, center_y: float):
        mouth_y = center_y + self.s(68)
        if self.mouth_open > 1.5:
            open_factor = min(1.0, max(0.1, self.mouth_open / 16.0))
            mouth_w = self.s(96.0)
            open_h = self.s(8.0 + open_factor * 26.0)
            y_top = mouth_y - self.s(3.0)

            # Khung miệng (môi trên và môi dưới)
            p0_top = (self.cx - mouth_w / 2, y_top)
            p1_top = (self.cx, y_top + self.s(2.5))
            p2_top = (self.cx + mouth_w / 2, y_top)
            top_pts = get_bezier_points(p0_top, p1_top, p2_top, 24)

            p0_bot = (self.cx + mouth_w / 2, y_top)
            p1_bot = (self.cx, y_top + open_h * 1.35)
            p2_bot = (self.cx - mouth_w / 2, y_top)
            bottom_pts = get_bezier_points(p0_bot, p1_bot, p2_bot, 28)

            mouth_poly = top_pts + bottom_pts[1:]
            pygame.draw.polygon(self.surface, self.ink_color, mouth_poly)

            # Lưỡi ở đáy miệng
            y_center_bottom = (y_top + (y_top + open_h * 1.35)) / 2.0
            mouth_depth = y_center_bottom - y_top
            tongue_w = mouth_w * 0.45
            tongue_h = mouth_depth * 0.38
            bot_tongue_slice = [
                pt for pt in bottom_pts
                if (self.cx - tongue_w / 2) <= pt[0] <= (self.cx + tongue_w / 2)
            ]

            if len(bot_tongue_slice) >= 2:
                pt_r = bot_tongue_slice[0]
                pt_l = bot_tongue_slice[-1]
                quarter_w = tongue_w / 4.0
                peak_y = y_center_bottom - tongue_h
                dip_y = peak_y + tongue_h * 0.18

                t_left_arc = get_bezier_points(pt_l, (self.cx - quarter_w, peak_y), (self.cx, dip_y), 16)
                t_right_arc = get_bezier_points((self.cx, dip_y), (self.cx + quarter_w, peak_y), pt_r, 16)
                tongue_poly = t_left_arc + t_right_arc[1:] + bot_tongue_slice
                tongue_color = (235, 122, 127)
                pygame.draw.polygon(self.surface, tongue_color, tongue_poly)

            # Răng (Teeth) từ mã nguồn gốc
            rx = self.cx + mouth_w / 2
            lx = self.cx - mouth_w / 2
            tooth_w = self.s(16.0)
            gap = self.s(3.0)
            tooth_depth = min(open_h * 0.45, self.s(12.5))
            taper_depth = tooth_depth * 0.45
            r = self.s(3.5)

            p_r_corner = (rx - self.s(5), y_top + self.s(3))
            p_r_out = (self.cx + gap / 2 + tooth_w, y_top + taper_depth)

            p_rt_b1 = (self.cx + gap / 2 + tooth_w, y_top + tooth_depth - r)
            p_rt_c1 = (self.cx + gap / 2 + tooth_w, y_top + tooth_depth)
            p_rt_b2 = (self.cx + gap / 2 + tooth_w - r, y_top + tooth_depth)
            p_rt_b3 = (self.cx + gap / 2 + r, y_top + tooth_depth)
            p_rt_c2 = (self.cx + gap / 2, y_top + tooth_depth)
            p_rt_b4 = (self.cx + gap / 2, y_top + tooth_depth - r)

            p_notch = (self.cx, y_top + tooth_depth * 0.25)

            p_lt_b4 = (self.cx - gap / 2, y_top + tooth_depth - r)
            p_lt_c2 = (self.cx - gap / 2, y_top + tooth_depth)
            p_lt_b3 = (self.cx - gap / 2 - r, y_top + tooth_depth)
            p_lt_b2 = (self.cx - gap / 2 - tooth_w + r, y_top + tooth_depth)
            p_lt_c1 = (self.cx - gap / 2 - tooth_w, y_top + tooth_depth)
            p_lt_b1 = (self.cx - gap / 2 - tooth_w, y_top + tooth_depth - r)

            p_l_out = (self.cx - gap / 2 - tooth_w, y_top + taper_depth)
            p_l_corner = (lx + self.s(5), y_top + self.s(3))

            pts_rt_corner1 = get_bezier_points(p_rt_b1, p_rt_c1, p_rt_b2, 6)
            pts_rt_corner2 = get_bezier_points(p_rt_b3, p_rt_c2, p_rt_b4, 6)
            pts_lt_corner2 = get_bezier_points(p_lt_b4, p_lt_c2, p_lt_b3, 6)
            pts_lt_corner1 = get_bezier_points(p_lt_b2, p_lt_c1, p_lt_b1, 6)

            teeth_bot_pts = (
                [p_r_corner, p_r_out] +
                pts_rt_corner1 + pts_rt_corner2 +
                [p_notch] +
                pts_lt_corner2 + pts_lt_corner1 +
                [p_l_out, p_l_corner]
            )
            teeth_poly = top_pts + teeth_bot_pts
            pygame.draw.polygon(self.surface, self.teeth_color, teeth_poly)

            # Viền sắc nét cho khuôn miệng
            line_w = max(1, int(self.s(4.5)))
            pygame.draw.lines(self.surface, self.ink_color, False, top_pts, line_w)
            pygame.draw.lines(self.surface, self.ink_color, False, bottom_pts, line_w)
            pygame.draw.circle(self.surface, self.ink_color, (int(self.cx - mouth_w / 2), int(y_top)), int(self.s(2.5)))
            pygame.draw.circle(self.surface, self.ink_color, (int(self.cx + mouth_w / 2), int(y_top)), int(self.s(2.5)))


        else:
            width = self.s(64)
            pts = []
            steps = 24
            for i in range(steps + 1):
                x = self.cx - width / 2 + (i / steps) * width
                angle = (i / steps) * 2 * math.pi
                y = mouth_y + math.sin(angle) * self.s(5.5)
                pts.append((x, y))
            pygame.draw.lines(self.surface, self.ink_color, False, pts, max(1, int(self.s(6))))
            pygame.draw.circle(self.surface, self.ink_color, (int(pts[0][0]), int(pts[0][1])), max(1, int(self.s(3))))
            pygame.draw.circle(self.surface, self.ink_color, (int(pts[-1][0]), int(pts[-1][1])), max(1, int(self.s(3))))

    def draw(self, surface: pygame.Surface = None):
        if surface is not None:
            self.surface = surface

        self.surface.fill(self.bg_color)
        center_y = self.cy + math.sin(self.breath_phase) * self.s(3.0)
        self.draw_eyebrows(center_y)
        self.draw_eyes(center_y)
        self.draw_blush(center_y)
        self.draw_mouth(center_y)


class FaceScreen(BaseScreen):
    """Màn hình hiển thị khuôn mặt Robot Anime chính và Studio Tùy biến Màu sắc & Biểu cảm."""

    EXPRESSIONS = [
        ("IDLE", "Mặc định", "IDLE • Tự động thở & chớp mắt"),
        ("ACTIVE", "Năng động", "ACTIVE • Mắt mở to tương tác"),
        ("SPEAKING", "Đang nói", "SPEAKING • Khẩu hình cử động"),
        ("LISTENING", "Lắng nghe", "LISTENING • Rướn mày chú ý"),
        ("THINKING", "Suy nghĩ", "THINKING • Nhíu mày tập trung"),
        ("WAKEWORD", "Đánh thức", "WAKEWORD • Sẵn sàng khẩu lệnh"),
        ("SLEEP", "Đi ngủ", "SLEEP • Nhắm nghiền thư giãn"),
        ("ACTING", "Hành động", "ACTING • Thực thi động tác"),
    ]

    THEME_PRESETS = [
        {
            "id": "bd1_classic",
            "name": "BD-1 Classic",
            "ink": (24, 61, 48),       # Forest Green
            "bg": (245, 247, 244),     # Snow White
            "teeth": (255, 255, 255),
        },
        {
            "id": "cyber_cyan",
            "name": "Cyber Cyan",
            "ink": (0, 229, 255),      # Neon Cyan
            "bg": (18, 22, 28),        # Deep Dark
            "teeth": (255, 255, 255),
        },
        {
            "id": "amber_glow",
            "name": "Amber Glow",
            "ink": (255, 179, 0),      # Warm Amber
            "bg": (24, 20, 20),        # Dark Charcoal
            "teeth": (255, 255, 255),
        },
        {
            "id": "sakura_pink",
            "name": "Sakura Pink",
            "ink": (233, 30, 99),      # Sakura Pink
            "bg": (253, 248, 247),     # Soft Rose White
            "teeth": (255, 255, 255),
        },
        {
            "id": "ocean_tech",
            "name": "Ocean Tech",
            "ink": (24, 144, 255),     # Tech Blue
            "bg": (240, 247, 255),     # Ice Blue
            "teeth": (255, 255, 255),
        },
        {
            "id": "matrix_lime",
            "name": "Matrix Lime",
            "ink": (46, 213, 115),     # Bright Lime
            "bg": (10, 20, 15),        # Midnight Green
            "teeth": (255, 255, 255),
        },
        {
            "id": "purple_dream",
            "name": "Purple Dream",
            "ink": (155, 89, 182),     # Soft Violet
            "bg": (248, 245, 252),     # Soft Lavender
            "teeth": (255, 255, 255),
        },
        {
            "id": "mono_dark",
            "name": "Dark Minimal",
            "ink": (240, 240, 240),    # Pure White
            "bg": (15, 15, 15),        # OLED Black
            "teeth": (160, 160, 160),
        },
    ]

    EYE_PALETTE = [
        (24, 61, 48),    # Forest Green
        (0, 229, 255),   # Cyber Cyan
        (255, 179, 0),   # Amber
        (233, 30, 99),   # Sakura Pink
        (24, 144, 255),  # Ocean Blue
        (46, 213, 115),  # Matrix Lime
        (155, 89, 182),  # Purple
        (240, 240, 240), # White
        (35, 35, 35),    # Charcoal
    ]

    BG_PALETTE = [
        (245, 247, 244), # Snow White
        (246, 241, 230), # Warm Cream
        (235, 245, 238), # Soft Mint
        (248, 245, 252), # Lavender
        (240, 247, 255), # Ice Blue
        (15, 17, 21),    # Dark OLED
        (28, 32, 38),    # Space Charcoal
        (10, 20, 15),    # Midnight Green
        (14, 22, 34),    # Midnight Navy
    ]

    def __init__(self, app_manager, show_gallery: bool = False):
        super().__init__(app_manager)
        self.is_gallery_screen = show_gallery
        self.show_gallery = show_gallery

        # Màu sắc mặc định
        self.current_ink = Colors.COLOR_INK
        self.current_bg = Colors.COLOR_BG
        self.current_teeth = Colors.COLOR_TEETH
        self.current_preset_id = "bd1_classic"

        # Khuôn mặt toàn màn hình chính
        self.face = AnimeRobotFace(
            app_manager.screen,
            cx=400,
            cy=225,
            scale=2.1,
            ink_color=self.current_ink,
            bg_color=self.current_bg,
            teeth_color=self.current_teeth,
        )

        # Tab và màn hình Studio Customizer
        self.current_tab = "themes"  # "themes" hoặc "expressions"
        self.toast_msg = ""
        self.toast_timer = 0.0

        # Surface preview nhỏ riêng biệt cho Studio
        self.preview_surface = pygame.Surface((286, 220))
        self.preview_face = AnimeRobotFace(
            self.preview_surface,
            cx=143,
            cy=105,
            scale=0.82,
            ink_color=self.current_ink,
            bg_color=self.current_bg,
            teeth_color=self.current_teeth,
        )

        # Cấu hình Rects tương tác
        self.back_rect = pygame.Rect(20, 16, 120, 42)
        self.tab_pill_rect = pygame.Rect(342, 68, 442, 42)
        self.tab_themes_rect = pygame.Rect(345, 71, 216, 36)
        self.tab_expr_rect = pygame.Rect(565, 71, 216, 36)
        self.btn_blink_rect = pygame.Rect(32, 374, 138, 38)
        self.btn_apply_main_rect = pygame.Rect(180, 374, 138, 38)

        self.preset_rects: List[Tuple[pygame.Rect, dict]] = []
        self.eye_swatch_rects: List[Tuple[pygame.Rect, Tuple[int, int, int]]] = []
        self.bg_swatch_rects: List[Tuple[pygame.Rect, Tuple[int, int, int]]] = []
        self.expr_rects: List[Tuple[pygame.Rect, str, str, str]] = []

        self._layout_studio()
        self.load_theme_settings()

    def _layout_studio(self):
        # 1. Presets (2 cột x 4 hàng)
        self.preset_rects.clear()
        for idx, preset in enumerate(self.THEME_PRESETS):
            col = idx % 2
            row = idx // 2
            x = 345 + col * 221
            y = 138 + row * 40
            self.preset_rects.append((pygame.Rect(x, y, 214, 34), preset))

        # 2. Color swatches cho Mắt (Ink) và Nền (Bg)
        self.eye_swatch_rects.clear()
        for idx, col in enumerate(self.EYE_PALETTE):
            cx = 398 + idx * 41
            cy = 344
            self.eye_swatch_rects.append((pygame.Rect(cx - 16, cy - 16, 32, 32), col))

        self.bg_swatch_rects.clear()
        for idx, col in enumerate(self.BG_PALETTE):
            cx = 398 + idx * 41
            cy = 392
            self.bg_swatch_rects.append((pygame.Rect(cx - 16, cy - 16, 32, 32), col))

        # 3. Expression cards (2 cột x 4 hàng)
        self.expr_rects.clear()
        for idx, (code, label, desc) in enumerate(self.EXPRESSIONS):
            col = idx % 2
            row = idx // 2
            x = 345 + col * 221
            y = 146 + row * 74
            self.expr_rects.append((pygame.Rect(x, y, 214, 66), code, label, desc))

    def load_theme_settings(self):
        """Nạp cấu hình màu sắc từ SQLite (FaceThemeRepository)."""
        from database.repositories import FaceThemeRepository
        theme = FaceThemeRepository.get_active_theme()

        ink = theme.get("ink_rgb", Colors.COLOR_INK)
        bg = theme.get("bg_rgb", Colors.COLOR_BG)
        teeth = theme.get("teeth_rgb", Colors.COLOR_TEETH)
        preset_id = theme.get("theme_id", "default")

        self.current_ink = tuple(ink)
        self.current_bg = tuple(bg)
        self.current_teeth = tuple(teeth)
        self.current_preset_id = preset_id

        self.face.set_colors(ink_color=self.current_ink, bg_color=self.current_bg, teeth_color=self.current_teeth)
        if hasattr(self, "preview_face") and self.preview_face:
            self.preview_face.set_colors(ink_color=self.current_ink, bg_color=self.current_bg, teeth_color=self.current_teeth)

    def apply_theme(
        self,
        ink: Tuple[int, int, int],
        bg: Tuple[int, int, int],
        teeth: Optional[Tuple[int, int, int]] = None,
        preset_id: Optional[str] = None,
    ):
        """Áp dụng màu sắc mới, cập nhật giao diện và lưu vĩnh viễn vào settings."""
        if teeth is None:
            lum_ink = 0.299 * ink[0] + 0.587 * ink[1] + 0.114 * ink[2]
            teeth = (160, 160, 160) if lum_ink > 220 else (255, 255, 255)

        self.current_ink = ink
        self.current_bg = bg
        self.current_teeth = teeth
        self.current_preset_id = preset_id

        # Áp dụng cho preview face
        self.preview_face.set_colors(ink_color=ink, bg_color=bg, teeth_color=teeth)

        # Áp dụng cho mặt chính
        main_scr = self.app_manager.screens.get("face")
        if main_scr and hasattr(main_scr, "face"):
            main_scr.face.set_colors(ink_color=ink, bg_color=bg, teeth_color=teeth)
        self.face.set_colors(ink_color=ink, bg_color=bg, teeth_color=teeth)

        # Lưu vào SQLite thông qua FaceThemeRepository
        from database.repositories import FaceThemeRepository
        hex_ink = FaceThemeRepository.rgb_to_hex(ink)
        hex_bg = FaceThemeRepository.rgb_to_hex(bg)
        hex_teeth = FaceThemeRepository.rgb_to_hex(teeth)
        theme_id = preset_id or "custom_user"
        theme_name = preset_id.replace("_", " ").title() if preset_id else "Custom"
        FaceThemeRepository.save_theme(theme_id, theme_name, hex_ink, hex_bg, hex_teeth, is_active=0)
        FaceThemeRepository.set_active_theme(theme_id)

        self.toast_msg = "✓ Đã áp dụng & lưu cấu hình!"
        self.toast_timer = time.monotonic() + 2.5

    def on_enter(self, gallery: Optional[bool] = None, **kwargs):
        if gallery is not None:
            self.show_gallery = gallery
        else:
            self.show_gallery = self.is_gallery_screen

        self.load_theme_settings()
        if not self.show_gallery:
            self.face.set_state("ACTIVE")
        else:
            self.preview_face.set_state("ACTIVE")

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.show_gallery:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos

            # Nút quay lại
            if self.back_rect.collidepoint(pos):
                self.app_manager.switch_screen("face")
                return True

            # Chuyển Tab
            if self.tab_themes_rect.collidepoint(pos):
                self.current_tab = "themes"
                return True
            if self.tab_expr_rect.collidepoint(pos):
                self.current_tab = "expressions"
                return True

            # Nút điều khiển Preview (bên trái)
            if self.btn_blink_rect.collidepoint(pos):
                self.preview_face.trigger_blink()
                return True

            if self.btn_apply_main_rect.collidepoint(pos):
                self.app_manager.set_face_state(self.preview_face.current_state)
                self.toast_msg = "✓ Đã đặt biểu cảm cho Robot!"
                self.toast_timer = time.monotonic() + 2.0
                return True

            # Tab Màu sắc & Themes
            if self.current_tab == "themes":
                # Click Preset
                for rect, preset in self.preset_rects:
                    if rect.collidepoint(pos):
                        self.apply_theme(
                            ink=preset["ink"],
                            bg=preset["bg"],
                            teeth=preset.get("teeth"),
                            preset_id=preset["id"],
                        )
                        return True

                # Click Swatch Mắt
                for rect, col in self.eye_swatch_rects:
                    if rect.collidepoint(pos):
                        self.apply_theme(
                            ink=col,
                            bg=self.current_bg,
                            teeth=self.current_teeth,
                            preset_id="custom",
                        )
                        return True

                # Click Swatch Nền
                for rect, col in self.bg_swatch_rects:
                    if rect.collidepoint(pos):
                        self.apply_theme(
                            ink=self.current_ink,
                            bg=col,
                            teeth=self.current_teeth,
                            preset_id="custom",
                        )
                        return True

            # Tab Thử Biểu cảm
            elif self.current_tab == "expressions":
                for rect, code, _, _ in self.expr_rects:
                    if rect.collidepoint(pos):
                        self.preview_face.set_state(code)
                        return True

        return False

    def update(self):
        if not self.show_gallery:
            self.face.update()
        else:
            self.preview_face.update()

    def draw(self, surface: pygame.Surface):
        if not self.show_gallery:
            self.face.draw(surface)
        else:
            self._draw_studio(surface)

    def _draw_studio(self, surface: pygame.Surface):
        surface.fill(Colors.PAGE_BG)

        # -------------------------------------------------------------
        # 1. TOP HEADER BAR
        # -------------------------------------------------------------
        # Nút Quay lại
        mouse_pos = pygame.mouse.get_pos()
        hover_back = self.back_rect.collidepoint(mouse_pos)
        bg_btn = Colors.CARD_BG_MUTED if hover_back else Colors.CARD_BG
        pygame.draw.rect(surface, bg_btn, self.back_rect, border_radius=12)
        pygame.draw.rect(surface, Colors.CARD_BORDER, self.back_rect, 1, border_radius=12)

        pygame.draw.line(surface, Colors.TEXT_DARK, (self.back_rect.x + 18, self.back_rect.centery), (self.back_rect.x + 28, self.back_rect.centery), 2)
        pygame.draw.line(surface, Colors.TEXT_DARK, (self.back_rect.x + 18, self.back_rect.centery), (self.back_rect.x + 24, self.back_rect.centery - 5), 2)
        pygame.draw.line(surface, Colors.TEXT_DARK, (self.back_rect.x + 18, self.back_rect.centery), (self.back_rect.x + 24, self.back_rect.centery + 5), 2)
        ts_back = self.theme.font_body_bold.render("Quay lại", True, Colors.TEXT_DARK)
        surface.blit(ts_back, (self.back_rect.x + 36, self.back_rect.centery - ts_back.get_height() // 2))

        # Tiêu đề & Phụ đề
        t_title = self.theme.font_h2.render("Tùy biến Khuôn mặt & Biểu cảm", True, Colors.TEXT_DARK)
        surface.blit(t_title, (155, 14))
        t_sub = self.theme.font_small.render("Tùy chỉnh màu mắt, màu nền và kiểm tra chuyển động khuôn mặt Robot", True, Colors.TEXT_MUTED)
        surface.blit(t_sub, (155, 38))

        # Thông báo Toast / Trạng thái
        now = time.monotonic()
        if self.toast_msg and now < self.toast_timer:
            toast_surf = self.theme.font_small_bold.render(self.toast_msg, True, Colors.BADGE_TEXT_READY)
            toast_w = toast_surf.get_width() + 24
            toast_rect = pygame.Rect(780 - toast_w, 18, toast_w, 34)
            pygame.draw.rect(surface, Colors.BADGE_BG_READY, toast_rect, border_radius=17)
            pygame.draw.rect(surface, Colors.BTN_PRIMARY, toast_rect, 1, border_radius=17)
            surface.blit(toast_surf, (toast_rect.x + 12, toast_rect.centery - toast_surf.get_height() // 2))
        else:
            hint_save = self.theme.font_small.render("● Tự động lưu", True, Colors.TEXT_LIGHT)
            surface.blit(hint_save, (780 - hint_save.get_width() - 8, 26))

        # -------------------------------------------------------------
        # 2. LEFT COLUMN: PREVIEW KHUÔN MẶT ROBOT
        # -------------------------------------------------------------
        left_card = pygame.Rect(20, 72, 310, 396)
        pygame.draw.rect(surface, Colors.CARD_BG, left_card, border_radius=16)
        pygame.draw.rect(surface, Colors.CARD_BORDER, left_card, 1, border_radius=16)

        # Header trong Card Preview
        lbl_screen = self.theme.font_small_bold.render("MÀN HÌNH ROBOT", True, Colors.TEXT_MUTED)
        surface.blit(lbl_screen, (36, 84))

        # Badge Live
        badge_rect = pygame.Rect(left_card.right - 80, 81, 64, 20)
        pygame.draw.rect(surface, Colors.PINE_GREEN_LIGHT, badge_rect, border_radius=10)
        pygame.draw.circle(surface, Colors.BTN_PRIMARY, (badge_rect.x + 12, badge_rect.centery), 4)
        live_txt = self.theme.font_small_bold.render("LIVE", True, Colors.BTN_PRIMARY)
        surface.blit(live_txt, (badge_rect.x + 22, badge_rect.centery - live_txt.get_height() // 2))

        # Khung viền Bezel giả lập màn hình Robot
        bezel_rect = pygame.Rect(32, 106, 286, 220)
        self.preview_face.draw(self.preview_surface)
        surface.blit(self.preview_surface, (bezel_rect.x, bezel_rect.y))
        pygame.draw.rect(surface, (180, 190, 185), bezel_rect, 1, border_radius=10)

        # Hiển thị thông tin trạng thái & Màu hiện tại
        state_badge = pygame.Rect(32, 334, 286, 28)
        pygame.draw.rect(surface, Colors.CARD_BG_MUTED, state_badge, border_radius=8)
        lbl_cur_state = self.theme.font_small_bold.render(f"Trạng thái: {self.preview_face.current_state}", True, Colors.BTN_PRIMARY)
        surface.blit(lbl_cur_state, (42, state_badge.centery - lbl_cur_state.get_height() // 2))

        # Nút Chớp mắt
        hover_blink = self.btn_blink_rect.collidepoint(mouse_pos)
        b_blink_bg = Colors.CARD_BG_MUTED if hover_blink else Colors.CARD_BG
        pygame.draw.rect(surface, b_blink_bg, self.btn_blink_rect, border_radius=10)
        pygame.draw.rect(surface, Colors.CARD_BORDER, self.btn_blink_rect, 1, border_radius=10)
        t_blink = self.theme.font_small_bold.render("Chớp mắt", True, Colors.TEXT_DARK)
        surface.blit(t_blink, (self.btn_blink_rect.centerx - t_blink.get_width() // 2, self.btn_blink_rect.centery - t_blink.get_height() // 2))

        # Nút Đặt làm biểu cảm chính
        hover_apply = self.btn_apply_main_rect.collidepoint(mouse_pos)
        b_apply_bg = Colors.BTN_PRIMARY_HOVER if hover_apply else Colors.BTN_PRIMARY
        pygame.draw.rect(surface, b_apply_bg, self.btn_apply_main_rect, border_radius=10)
        t_apply = self.theme.font_small_bold.render("Đặt cho Robot", True, Colors.COLOR_WHITE)
        surface.blit(t_apply, (self.btn_apply_main_rect.centerx - t_apply.get_width() // 2, self.btn_apply_main_rect.centery - t_apply.get_height() // 2))

        hint_click = self.theme.font_small.render("Chạm các nút bên phải để đổi màu/biểu cảm", True, Colors.TEXT_LIGHT)
        surface.blit(hint_click, (left_card.centerx - hint_click.get_width() // 2, 424))

        # -------------------------------------------------------------
        # 3. RIGHT COLUMN: TABS & BẢNG ĐIỀU KHIỂN
        # -------------------------------------------------------------
        # Pill container cho tabs
        pygame.draw.rect(surface, Colors.CARD_BG_MUTED, self.tab_pill_rect, border_radius=21)
        pygame.draw.rect(surface, Colors.CARD_BORDER, self.tab_pill_rect, 1, border_radius=21)

        is_tab_themes = (self.current_tab == "themes")
        is_tab_expr = (self.current_tab == "expressions")

        # Active pill
        active_tab_rect = self.tab_themes_rect if is_tab_themes else self.tab_expr_rect
        pygame.draw.rect(surface, Colors.TEXT_DARK, active_tab_rect, border_radius=18)

        # Tab 1: Chủ đề & Cảm xúc
        txt_col1 = Colors.COLOR_WHITE if is_tab_themes else Colors.TEXT_MUTED
        txt_tab1 = (self.theme.font_body_bold if is_tab_themes else self.theme.font_body).render("Chủ đề & Cảm xúc", True, txt_col1)
        surface.blit(txt_tab1, (self.tab_themes_rect.centerx - txt_tab1.get_width() // 2, self.tab_themes_rect.centery - txt_tab1.get_height() // 2))

        # Tab 2: Thử biểu cảm
        txt_col2 = Colors.COLOR_WHITE if is_tab_expr else Colors.TEXT_MUTED
        txt_tab2 = (self.theme.font_body_bold if is_tab_expr else self.theme.font_body).render("Thử biểu cảm", True, txt_col2)
        surface.blit(txt_tab2, (self.tab_expr_rect.centerx - txt_tab2.get_width() // 2, self.tab_expr_rect.centery - txt_tab2.get_height() // 2))

        # Nội dung Tab
        if is_tab_themes:
            self._draw_tab_themes(surface)
        else:
            self._draw_tab_expressions(surface)

    def _draw_tab_themes(self, surface: pygame.Surface):
        # Tiêu đề mục 1: Chọn cảm xúc + hint bên phải
        lbl_presets = self.theme.font_title.render("Chọn cảm xúc", True, Colors.TEXT_DARK)
        surface.blit(lbl_presets, (348, 118))
        hint_cols = self.theme.font_small.render("Mực / Nền / Điểm nhấn", True, Colors.TEXT_MUTED)
        surface.blit(hint_cols, (780 - hint_cols.get_width(), 122))

        # Danh sách 8 Presets (2 cột x 4 hàng)
        for rect, preset in self.preset_rects:
            is_active = (
                self.current_preset_id == preset["id"]
                or (self.current_ink == preset["ink"] and self.current_bg == preset["bg"])
            )
            bg_col = Colors.PINE_GREEN_LIGHT if is_active else Colors.CARD_BG
            border_col = Colors.BTN_PRIMARY if is_active else Colors.CARD_BORDER
            border_w = 2 if is_active else 1

            pygame.draw.rect(surface, bg_col, rect, border_radius=10)
            pygame.draw.rect(surface, border_col, rect, border_w, border_radius=10)

            cy = rect.centery

            # Tên Preset (bên trái)
            txt_name = (self.theme.font_body_bold if is_active else self.theme.font_body).render(
                preset["name"], True, Colors.BTN_PRIMARY if is_active else Colors.TEXT_DARK
            )
            surface.blit(txt_name, (rect.x + 12, cy - txt_name.get_height() // 2))

            # 3 chấm màu: Mực, Nền, Điểm nhấn (teeth) + dấu tích tròn khi active
            teeth_col = preset.get("teeth", (255, 255, 255))
            if is_active:
                chk_cx = rect.right - 14
                pygame.draw.circle(surface, Colors.BTN_PRIMARY, (chk_cx, cy), 9)
                pygame.draw.lines(surface, Colors.COLOR_WHITE, False, [
                    (chk_cx - 4, cy),
                    (chk_cx - 1, cy + 3),
                    (chk_cx + 4, cy - 3)
                ], 2)
                dot_x = rect.right - 34
            else:
                dot_x = rect.right - 14

            for col in [teeth_col, preset["bg"], preset["ink"]]:
                pygame.draw.circle(surface, col, (dot_x, cy), 6)
                pygame.draw.circle(surface, (180, 185, 180), (dot_x, cy), 6, 1)
                dot_x -= 15

        # Tiêu đề mục 2: Tùy chỉnh của bạn + hint bên phải
        lbl_custom = self.theme.font_title.render("Tùy chỉnh của bạn", True, Colors.TEXT_DARK)
        surface.blit(lbl_custom, (348, 304))
        hint_touch = self.theme.font_small.render("Chạm chọn màu", True, Colors.TEXT_MUTED)
        surface.blit(hint_touch, (780 - hint_touch.get_width(), 308))

        # Row 1: Màu Mắt
        lbl_eye = self.theme.font_small_bold.render("Mắt:", True, Colors.TEXT_MUTED)
        surface.blit(lbl_eye, (348, 334))

        for rect, col in self.eye_swatch_rects:
            is_sel = (self.current_ink == col)
            cx, cy = rect.centerx, rect.centery
            if is_sel:
                pygame.draw.circle(surface, Colors.BTN_PRIMARY, (cx, cy), 16, 2)
                pygame.draw.circle(surface, col, (cx, cy), 13)
                lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
                tick_col = Colors.COLOR_WHITE if lum < 140 else (24, 61, 48)
                pygame.draw.lines(surface, tick_col, False, [
                    (cx - 4, cy), (cx - 1, cy + 3), (cx + 4, cy - 3)
                ], 2)
            else:
                pygame.draw.circle(surface, col, (cx, cy), 12)
                pygame.draw.circle(surface, (180, 185, 180), (cx, cy), 12, 1)

        # Row 2: Màu Nền
        lbl_bg = self.theme.font_small_bold.render("Nền:", True, Colors.TEXT_MUTED)
        surface.blit(lbl_bg, (348, 382))

        for rect, col in self.bg_swatch_rects:
            is_sel = (self.current_bg == col)
            cx, cy = rect.centerx, rect.centery
            if is_sel:
                pygame.draw.circle(surface, Colors.BTN_PRIMARY, (cx, cy), 16, 2)
                pygame.draw.circle(surface, col, (cx, cy), 13)
                lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
                tick_col = Colors.COLOR_WHITE if lum < 140 else (24, 61, 48)
                pygame.draw.lines(surface, tick_col, False, [
                    (cx - 4, cy), (cx - 1, cy + 3), (cx + 4, cy - 3)
                ], 2)
            else:
                pygame.draw.circle(surface, col, (cx, cy), 12)
                pygame.draw.circle(surface, (180, 185, 180), (cx, cy), 12, 1)

        # Chú thích
        hint_palette = self.theme.font_small.render("Chạm vào màu bất kỳ để áp dụng trực tiếp lên khuôn mặt Robot", True, Colors.TEXT_LIGHT)
        surface.blit(hint_palette, (348, 428))

    def _draw_tab_expressions(self, surface: pygame.Surface):
        lbl_intro = self.theme.font_title.render("Chọn trạng thái để xem cử động trên màn hình:", True, Colors.TEXT_DARK)
        surface.blit(lbl_intro, (348, 122))

        for rect, code, label, desc in self.expr_rects:
            is_sel = (self.preview_face.current_state == code)
            bg_col = Colors.PINE_GREEN_LIGHT if is_sel else Colors.CARD_BG
            border_col = Colors.BTN_PRIMARY if is_sel else Colors.CARD_BORDER
            border_w = 2 if is_sel else 1

            pygame.draw.rect(surface, bg_col, rect, border_radius=12)
            pygame.draw.rect(surface, border_col, rect, border_w, border_radius=12)

            # Tên biểu cảm (gọn gàng, không bao giờ đè lên badge)
            txt_l = (self.theme.font_body_bold if is_sel else self.theme.font_body).render(
                label, True, Colors.BTN_PRIMARY if is_sel else Colors.TEXT_DARK
            )
            surface.blit(txt_l, (rect.x + 14, rect.y + 12))

            # Mô tả chi tiết & State code
            txt_d = self.theme.font_small.render(desc, True, Colors.TEXT_MUTED)
            surface.blit(txt_d, (rect.x + 14, rect.y + 38))

            # Badge trạng thái "Đang diễn" độc lập ở góc phải
            if is_sel:
                badge_w = 78
                badge_h = 22
                badge_rect = pygame.Rect(rect.right - badge_w - 10, rect.y + 10, badge_w, badge_h)
                pygame.draw.rect(surface, (218, 235, 224), badge_rect, border_radius=11)
                pygame.draw.rect(surface, Colors.BTN_PRIMARY, badge_rect, 1, border_radius=11)
                pygame.draw.circle(surface, Colors.BTN_PRIMARY, (badge_rect.x + 10, badge_rect.centery), 3)
                badge_txt = self.theme.font_small_bold.render("Đang diễn", True, Colors.BTN_PRIMARY)
                surface.blit(badge_txt, (badge_rect.x + 18, badge_rect.centery - badge_txt.get_height() // 2))
