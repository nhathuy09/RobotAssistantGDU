import math
import random
import time
import pygame
from typing import List, Tuple
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


class AnimeRobotFace:
    """Đồ họa khuôn mặt Anime BD-1 sinh động với nhịp thở, chớp mắt và cử động miệng."""

    SCALE = 2.1
    VALID_STATES = ["IDLE", "ACTIVE", "LISTENING", "THINKING", "SPEAKING", "ACTING", "WAKEWORD", "SLEEP", "STANDBY"]

    def __init__(self, surface: pygame.Surface, cx: int = 400, cy: int = 225):
        self.surface = surface
        self.cx = cx
        self.cy = cy
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
        return value * self.SCALE

    def set_state(self, state: str):
        state = state.upper()
        if state in self.VALID_STATES and state != self.current_state:
            self.current_state = state
            self.state_enter_time = time.monotonic()

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
        cap_r = int(self.s(4))

        # Lông mày trái
        p0_l = (self.cx - self.s(110), brow_y + self.s(10))
        p1_l = (self.cx - self.s(75), brow_y - self.s(18))
        p2_l = (self.cx - self.s(38), brow_y + self.s(2))
        pts_left = get_bezier_points(p0_l, p1_l, p2_l)
        pygame.draw.lines(self.surface, Colors.COLOR_INK, False, pts_left, line_w)
        pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p0_l[0]), int(p0_l[1])), cap_r)
        pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p2_l[0]), int(p2_l[1])), cap_r)

        # Lông mày phải
        p0_r = (self.cx + self.s(38), brow_y + self.s(2))
        p1_r = (self.cx + self.s(75), brow_y - self.s(18))
        p2_r = (self.cx + self.s(110), brow_y + self.s(10))
        pts_right = get_bezier_points(p0_r, p1_r, p2_r)
        pygame.draw.lines(self.surface, Colors.COLOR_INK, False, pts_right, line_w)
        pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p0_r[0]), int(p0_r[1])), cap_r)
        pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p2_r[0]), int(p2_r[1])), cap_r)

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
            cap_r = int(self.s(4.0))

            p0_el = (lx - arc_w / 2, base_y - self.s(4.0) * t)
            p1_el = (lx, base_y + arc_depth)
            p2_el = (lx + arc_w / 2, base_y - self.s(4.0) * t)
            pts_el = get_bezier_points(p0_el, p1_el, p2_el, 20)
            pygame.draw.lines(self.surface, Colors.COLOR_INK, False, pts_el, line_w)
            pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p0_el[0]), int(p0_el[1])), cap_r)
            pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p2_el[0]), int(p2_el[1])), cap_r)

            p0_er = (rx - arc_w / 2, base_y - self.s(4.0) * t)
            p1_er = (rx, base_y + arc_depth)
            p2_er = (rx + arc_w / 2, base_y - self.s(4.0) * t)
            pts_er = get_bezier_points(p0_er, p1_er, p2_er, 20)
            pygame.draw.lines(self.surface, Colors.COLOR_INK, False, pts_er, line_w)
            pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p0_er[0]), int(p0_er[1])), cap_r)
            pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(p2_er[0]), int(p2_er[1])), cap_r)
        else:
            # Mắt mở hình chữ nhật bo tròn
            h = self.s(self.eye_h) * (1.0 - self.sleep_progress * 1.6)
            if self.is_blinking:
                factor = abs(self.blink_progress - 0.5) * 2.0
                h = max(self.s(6), self.s(self.eye_h) * factor)
            h = max(self.s(6), h)

            radius = int(eye_w / 2)
            rect_l = pygame.Rect(int(lx - eye_w / 2), int(center_y - h / 2), int(eye_w), int(h))
            rect_r = pygame.Rect(int(rx - eye_w / 2), int(center_y - h / 2), int(eye_w), int(h))
            pygame.draw.rect(self.surface, Colors.COLOR_INK, rect_l, border_radius=radius)
            pygame.draw.rect(self.surface, Colors.COLOR_INK, rect_r, border_radius=radius)

    def draw_blush(self, center_y: float):
        blush_y = center_y + self.s(46)
        dy = self.s(20)
        dx = self.s(7)
        line_w = max(1, int(self.s(6)))
        lx = self.cx - self.s(120)
        rx = self.cx + self.s(120)

        pygame.draw.line(self.surface, Colors.COLOR_INK, (lx - self.s(12), blush_y - dy / 2), (lx - self.s(12) + dx, blush_y + dy / 2), line_w)
        pygame.draw.line(self.surface, Colors.COLOR_INK, (lx + self.s(4), blush_y - dy / 2), (lx + self.s(4) + dx, blush_y + dy / 2), line_w)
        pygame.draw.line(self.surface, Colors.COLOR_INK, (rx - self.s(4), blush_y - dy / 2), (rx - self.s(4) + dx, blush_y + dy / 2), line_w)
        pygame.draw.line(self.surface, Colors.COLOR_INK, (rx + self.s(12), blush_y - dy / 2), (rx + self.s(12) + dx, blush_y + dy / 2), line_w)

    def draw_mouth(self, center_y: float):
        mouth_y = center_y + self.s(68)
        if self.mouth_open > 1.5:
            open_factor = min(1.0, max(0.1, self.mouth_open / 16.0))
            mouth_w = self.s(96.0)
            open_h = self.s(8.0 + open_factor * 26.0)
            y_top = mouth_y - self.s(3.0)

            top_pts = get_bezier_points((self.cx - mouth_w / 2, y_top), (self.cx, y_top + self.s(2.5)), (self.cx + mouth_w / 2, y_top), 24)
            bottom_pts = get_bezier_points((self.cx + mouth_w / 2, y_top), (self.cx, y_top + open_h * 1.35), (self.cx - mouth_w / 2, y_top), 28)
            pygame.draw.polygon(self.surface, Colors.COLOR_INK, top_pts + bottom_pts[1:])

            # Vẽ răng
            rx = self.cx + mouth_w / 2
            lx = self.cx - mouth_w / 2
            tooth_w = self.s(16.0)
            gap = self.s(3.0)
            tooth_depth = min(open_h * 0.45, self.s(12.5))
            r = self.s(3.5)

            p_r_corner = (rx - self.s(5), y_top + self.s(3))
            p_r_out = (self.cx + gap / 2 + tooth_w, y_top + tooth_depth * 0.45)
            p_notch = (self.cx, y_top + tooth_depth * 0.25)
            p_l_out = (self.cx - gap / 2 - tooth_w, y_top + tooth_depth * 0.45)
            p_l_corner = (lx + self.s(5), y_top + self.s(3))

            pts_rt = get_bezier_points((self.cx + gap / 2 + tooth_w, y_top + tooth_depth - r), (self.cx + gap / 2 + tooth_w, y_top + tooth_depth), (self.cx + gap / 2 + tooth_w - r, y_top + tooth_depth), 6)
            pts_lt = get_bezier_points((self.cx - gap / 2 - tooth_w + r, y_top + tooth_depth), (self.cx - gap / 2 - tooth_w, y_top + tooth_depth), (self.cx - gap / 2 - tooth_w, y_top + tooth_depth - r), 6)

            teeth_poly = top_pts + [p_r_corner, p_r_out] + pts_rt + [p_notch] + pts_lt + [p_l_out, p_l_corner]
            pygame.draw.polygon(self.surface, Colors.COLOR_TEETH, teeth_poly)

            line_w = max(1, int(self.s(4.5)))
            pygame.draw.lines(self.surface, Colors.COLOR_INK, False, top_pts, line_w)
            pygame.draw.lines(self.surface, Colors.COLOR_INK, False, bottom_pts, line_w)
        else:
            width = self.s(64)
            pts = []
            steps = 24
            for i in range(steps + 1):
                x = self.cx - width / 2 + (i / steps) * width
                angle = (i / steps) * 2 * math.pi
                y = mouth_y + math.sin(angle) * self.s(5.5)
                pts.append((x, y))
            pygame.draw.lines(self.surface, Colors.COLOR_INK, False, pts, max(1, int(self.s(6))))
            pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(pts[0][0]), int(pts[0][1])), int(self.s(3)))
            pygame.draw.circle(self.surface, Colors.COLOR_INK, (int(pts[-1][0]), int(pts[-1][1])), int(self.s(3)))

    def draw(self, surface: pygame.Surface = None):
        # Dùng surface được Screen Manager truyền vào để tránh vẽ nhầm surface.
        if surface is not None:
            self.surface = surface

        self.surface.fill(Colors.COLOR_BG)
        center_y = self.cy + math.sin(self.breath_phase) * self.s(3.0)
        self.draw_eyebrows(center_y)
        self.draw_eyes(center_y)
        self.draw_blush(center_y)
        self.draw_mouth(center_y)


class FaceScreen(BaseScreen):
    """Màn hình chính hiển thị khuôn mặt Robot Anime và Kho biểu cảm (Gallery)."""

    EXPRESSIONS = [
        ("IDLE", "Mặc định (IDLE)"),
        ("SPEAKING", "Đang nói (SPEAKING)"),
        ("LISTENING", "Lắng nghe (LISTENING)"),
        ("THINKING", "Suy nghĩ (THINKING)"),
        ("WAKEWORD", "Đánh thức (WAKEWORD)"),
        ("SLEEP", "Đi ngủ (SLEEP)"),
        ("ACTIVE", "Năng động (ACTIVE)"),
        ("ACTING", "Hành động (ACTING)"),
    ]

    def __init__(self, app_manager, show_gallery: bool = False):
        super().__init__(app_manager)
        self.face = AnimeRobotFace(app_manager.screen, cx=400, cy=225)
        self.show_gallery = show_gallery
        self.cards = []
        self._layout_gallery()

    def _layout_gallery(self):
        self.cards.clear()
        for idx, (code, label) in enumerate(self.EXPRESSIONS):
            col = idx % 2
            row = idx // 2
            rect = pygame.Rect(30 + col * 380, 75 + row * 78, 360, 68)
            self.cards.append((rect, code, label))

    def on_enter(self, gallery: bool = False, **kwargs):
        self.show_gallery = gallery
        if not gallery:
            self.face.set_state("ACTIVE")

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.show_gallery:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Nút quay lại
                back_rect = pygame.Rect(20, 22, 134, 48)
                if back_rect.collidepoint(event.pos):
                    self.show_gallery = False
                    return True

                # Chọn biểu cảm
                for rect, code, _ in self.cards:
                    if rect.collidepoint(event.pos):
                        self.face.set_state(code)
                        return True
        return False

    def update(self):
        self.face.update()

    def draw(self, surface: pygame.Surface):
        if not self.show_gallery:
            self.face.draw(surface)
        else:
            surface.fill(Colors.COLOR_BG)

            # Nút Quay lại
            back_rect = pygame.Rect(20, 22, 134, 48)
            mouse_pos = pygame.mouse.get_pos()
            hover_back = back_rect.collidepoint(mouse_pos)
            bg = (248, 246, 240) if hover_back else Colors.CARD_BG
            pygame.draw.rect(surface, bg, back_rect, border_radius=12)
            pygame.draw.rect(surface, Colors.CARD_BORDER, back_rect, 1, border_radius=12)
            pygame.draw.line(surface, Colors.COLOR_INK, (back_rect.x + 22, back_rect.centery), (back_rect.x + 34, back_rect.centery), 2)
            pygame.draw.line(surface, Colors.COLOR_INK, (back_rect.x + 22, back_rect.centery), (back_rect.x + 28, back_rect.centery - 6), 2)
            pygame.draw.line(surface, Colors.COLOR_INK, (back_rect.x + 22, back_rect.centery), (back_rect.x + 28, back_rect.centery + 6), 2)
            ts = self.theme.font_small.render("Quay lại", True, Colors.COLOR_INK)
            surface.blit(ts, (back_rect.x + 40, back_rect.centery - ts.get_height() // 2))

            # Tiêu đề
            title = self.theme.font_h2.render("Kho Biểu cảm Khuôn mặt (Chạm để xem thử)", True, Colors.TEXT_DARK)
            surface.blit(title, (170, 28))

            # Danh sách card biểu cảm
            for rect, code, label in self.cards:
                is_sel = (self.face.current_state == code)
                pygame.draw.rect(surface, Colors.CARD_BG, rect, border_radius=14)
                border_col = Colors.BTN_PRIMARY if is_sel else Colors.CARD_BORDER
                border_w = 2 if is_sel else 1
                pygame.draw.rect(surface, border_col, rect, border_w, border_radius=14)

                c_surf = self.theme.font_body_bold.render(label, True, Colors.BTN_PRIMARY if is_sel else Colors.TEXT_DARK)
                surface.blit(c_surf, (rect.x + 20, rect.y + 14))

                sub = self.theme.font_small.render(f"State: {code}", True, Colors.TEXT_MUTED)
                surface.blit(sub, (rect.x + 20, rect.y + 40))

                if is_sel:
                    badge = self.theme.font_small_bold.render("● Đang kích hoạt", True, Colors.BTN_PRIMARY)
                    surface.blit(badge, (rect.right - 140, rect.y + 24))
