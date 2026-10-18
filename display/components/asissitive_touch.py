import math
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import pygame
from display.components.base_widget import BaseWidget
from display.theme import Colors


class AssistiveTouch(BaseWidget):
    ICON_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "icon"
    FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

    MENU_W = 336
    MENU_H = 406
    MENU_MARGIN = 10
    MENU_GAP = 18
    DRAG_THRESHOLD = 10
    HIT_RADIUS = 36

    IDLE_ALPHA = 0.32
    HOLD_MS = 1500
    FADE_SPEED = 0.2

    ITEMS = [
        {"id": "face", "label": "Trang chủ", "icon": "home"},
        {"id": "wifi", "label": "Wi-Fi", "icon": "wifi"},
        {"id": "persona", "label": "Cấu hình", "icon": "config"},
        {"id": "faces_gallery", "label": "Biểu cảm", "icon": "face"},
        {"id": "system", "label": "Hệ thống", "icon": "system"},
        {"id": "close", "label": "Đóng", "icon": "exit"},
    ]

    ICON_MAP = {
        "home": ["house.png", "home.png", "house.svg", "home.svg"],
        "wifi": ["wifi.png", "wifi.svg"],
        "config": ["config.png", "config.svg", "persona.png", "persona.svg"],
        "persona": ["config.png", "persona.png", "config.svg", "persona.svg"],
        "face": ["face.png", "face.svg", "faces.png", "faces.svg"],
        "faces": ["face.png", "faces.png", "face.svg", "faces.svg"],
        "system": ["system.png", "system.svg", "gear.png", "gear.svg", "settings.png"],
        "exit": ["exit.png", "exit.svg", "close.png", "close.svg"],
        "close": ["exit.png", "close.png", "exit.svg", "close.svg", "back.png", "back.svg"],
        "back": ["back.png", "back.svg"],
    }

    def __init__(
        self,
        screen_size: Tuple[int, int] = (800, 480),
        on_navigate: Optional[Callable[[str], None]] = None,
    ):
        self.screen_w, self.screen_h = screen_size
        center_x, center_y = self.screen_w // 2, self.screen_h - 45
        super().__init__(pygame.Rect(center_x - 32, center_y - 32, 64, 64))

        self.pos = [float(center_x), float(center_y)]
        self.on_navigate = on_navigate

        self.menu_open = False
        self.animation_progress = 0.0
        self.animation_origin = (center_x, center_y)

        self.is_dragging = False
        self.has_dragged = False
        self.drag_start = (0, 0)

        self.alpha = self.IDLE_ALPHA
        self.last_touch_ms = -10**9

        font_path = self.FONT_DIR / "Inter_18pt-SemiBold.ttf"
        if font_path.exists():
            self.font_title = pygame.font.Font(str(font_path), 16)
            self.font_label = pygame.font.Font(str(font_path), 14)
        else:
            self.font_title = pygame.font.SysFont("Segoe UI", 16, bold=True)
            self.font_label = pygame.font.SysFont("Segoe UI", 14, bold=True)

        self._icon_cache: Dict[Tuple[str, int, Tuple[int, int, int]], pygame.Surface] = {}

        self.current_screen_id = "face"

    def compute_menu_rect(self) -> pygame.Rect:
        scale = min(
            self.screen_w / 800,
            self.screen_h / 480,
            (self.screen_w - self.MENU_MARGIN * 2) / self.MENU_W,
            (self.screen_h - self.MENU_MARGIN * 2) / self.MENU_H,
        )
        w = round(self.MENU_W * scale)
        h = round(self.MENU_H * scale)

        top_space = self.pos[1] - self.MENU_MARGIN - self.MENU_GAP
        bot_space = self.screen_h - self.MENU_MARGIN - self.MENU_GAP - self.pos[1]

        if max(top_space, bot_space) >= h:
            x = round(self.pos[0] - w / 2)
            y = round(self.pos[1] - self.MENU_GAP - h) if top_space >= bot_space else round(self.pos[1] + self.MENU_GAP)
        else:
            left_space = self.pos[0] - self.MENU_MARGIN - self.MENU_GAP
            right_space = self.screen_w - self.MENU_MARGIN - self.MENU_GAP - self.pos[0]
            x = round(self.pos[0] - self.MENU_GAP - w) if left_space >= right_space else round(self.pos[0] + self.MENU_GAP)
            y = round(self.pos[1] - h / 2)

        x = max(self.MENU_MARGIN, min(self.screen_w - w - self.MENU_MARGIN, x))
        y = max(self.MENU_MARGIN, min(self.screen_h - h - self.MENU_MARGIN, y))
        return pygame.Rect(x, y, w, h)

    def _item_center(self, index: int, rect: pygame.Rect) -> Tuple[int, int]:
        col, row = index % 2, index // 2
        x_ratio = 0.27 if col == 0 else 0.73
        y_ratio = (0.235, 0.505, 0.78)[row]
        return round(rect.x + rect.w * x_ratio), round(rect.y + rect.h * y_ratio)

    def _item_hit_rect(self, index: int, rect: pygame.Rect) -> pygame.Rect:
        cx, cy = self._item_center(index, rect)
        return pygame.Rect(
            round(cx - rect.w * 0.21),
            round(cy - rect.h * 0.12),
            round(rect.w * 0.42),
            round(rect.h * 0.27),
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.menu_open:
                menu_rect = self.compute_menu_rect()
                clicked_item = False
                for idx, item in enumerate(self.ITEMS):
                    if self._item_hit_rect(idx, menu_rect).collidepoint(pos):
                        self.animation_origin = self._item_center(idx, menu_rect)
                        if item["id"] == "close":
                            self.menu_open = False
                        else:
                            self.current_screen_id = item["id"]
                            self.menu_open = False
                            if self.on_navigate:
                                self.on_navigate(item["id"])
                        clicked_item = True
                        return True

                if not clicked_item:
                    if not menu_rect.collidepoint(pos):
                        self.menu_open = False
                        return True
            else:
                dist = math.hypot(pos[0] - self.pos[0], pos[1] - self.pos[1])
                if dist <= self.HIT_RADIUS:
                    self.is_dragging = True
                    self.drag_start = pos
                    self.has_dragged = False
                    self.last_touch_ms = pygame.time.get_ticks()
                    return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                self.last_touch_ms = pygame.time.get_ticks()
                dx = event.pos[0] - self.drag_start[0]
                dy = event.pos[1] - self.drag_start[1]
                if math.hypot(dx, dy) > self.DRAG_THRESHOLD:
                    self.has_dragged = True
                    self.pos[0] = max(35, min(self.screen_w - 35, event.pos[0]))
                    self.pos[1] = max(35, min(self.screen_h - 35, event.pos[1]))
                    self.rect.center = (int(self.pos[0]), int(self.pos[1]))
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging:
                self.last_touch_ms = pygame.time.get_ticks()
                if not self.has_dragged:
                    self.animation_origin = (int(self.pos[0]), int(self.pos[1]))
                    self.animation_progress = 0.0
                    self.menu_open = True
                self.is_dragging = False
                return True

        return False

    def update(self):
        # Cập nhật animation của popup menu
        speed = 0.14
        if self.menu_open:
            self.animation_progress = min(1.0, self.animation_progress + speed)
        else:
            self.animation_progress = max(0.0, self.animation_progress - speed)

        # Cập nhật alpha cho nút nổi
        now = pygame.time.get_ticks()
        touched = self.is_dragging or self.menu_open or (now - self.last_touch_ms) < self.HOLD_MS
        target_alpha = 1.0 if touched else self.IDLE_ALPHA
        self.alpha += (target_alpha - self.alpha) * self.FADE_SPEED

    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        # Vẽ Menu nếu đang animate mở
        if self.animation_progress > 0:
            self._draw_menu(surface)

        # Vẽ nút AssistiveTouch khi menu không che
        if not self.menu_open:
            self._draw_button(surface)

    def _draw_button(self, surface: pygame.Surface):
        cx, cy = int(self.pos[0]), int(self.pos[1])
        btn_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        bcx, bcy = 32, 32

        def a(base):
            return max(0, min(255, int(base * self.alpha)))

        pygame.draw.circle(btn_surf, (35, 45, 56, a(195)), (bcx, bcy), 29)
        pygame.draw.circle(btn_surf, (68, 82, 96, a(215)), (bcx, bcy), 23)
        pygame.draw.circle(btn_surf, (140, 155, 170, a(235)), (bcx, bcy), 17)
        pygame.draw.circle(btn_surf, (255, 255, 255, a(255)), (bcx, bcy), 11)

        surface.blit(btn_surf, (cx - 32, cy - 32))

    def _draw_menu(self, surface: pygame.Surface):
        p = self.animation_progress
        eased_p = p**2 * (3 - 2 * p)

        # 1. Overlay tối màu
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((43, 48, 58, round(56 * eased_p)))
        surface.blit(overlay, (0, 0))

        # 2. Khung menu
        rect = self.compute_menu_rect()
        panel_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (247, 245, 240), (0, 0, rect.w, rect.h), border_radius=26)
        pygame.draw.rect(panel_surf, (213, 215, 210), (0, 0, rect.w, rect.h), 1, border_radius=26)

        title = self.font_title.render("Điều khiển nhanh", True, Colors.TEXT_DARK)
        panel_surf.blit(title, (rect.w // 2 - title.get_width() // 2, round(rect.h * 0.068)))

        # 3. Vẽ các icon & label
        for idx, item in enumerate(self.ITEMS):
            icx, icy = self._item_center(idx, pygame.Rect(0, 0, rect.w, rect.h))
            is_active = (item["id"] == self.current_screen_id)
            radius = round(rect.w * 0.102)

            icon_bg, icon_col = {
                "home": ((232, 237, 240), Colors.MENU_SLATE),
                "wifi": ((232, 237, 240), Colors.MENU_SLATE),
                "config": (Colors.GREEN_BG, Colors.GREEN_ICON),
                "persona": (Colors.GREEN_BG, Colors.GREEN_ICON),
                "face": (Colors.GREEN_BG, Colors.GREEN_ICON),
                "faces": (Colors.GREEN_BG, Colors.GREEN_ICON),
                "system": ((232, 237, 240), Colors.MENU_SLATE),
                "exit": (Colors.MENU_WARM_BG, Colors.TEXT_DARK),
                "close": (Colors.MENU_WARM_BG, Colors.TEXT_DARK),
            }.get(item["icon"], ((232, 237, 240), Colors.MENU_SLATE))

            if is_active:
                icon_bg = Colors.GREEN_TEXT
                icon_col = Colors.COLOR_WHITE

            pygame.draw.circle(panel_surf, icon_bg, (icx, icy), radius)
            outline = Colors.MENU_SLATE if is_active else Colors.CARD_BORDER
            pygame.draw.circle(panel_surf, outline, (icx, icy), radius, 2 if is_active else 1)

            target_icon_size = max(18, round(radius * 0.82))
            self._draw_icon(panel_surf, item["icon"], icx, icy, icon_col, target_size=target_icon_size)

            lbl_col = Colors.GREEN_TEXT if is_active else Colors.TEXT_DARK
            lbl = self.font_label.render(item["label"], True, lbl_col)
            panel_surf.blit(lbl, (icx - lbl.get_width() // 2, icy + radius + round(rect.h * 0.025)))

        # 4. Phóng to và di chuyển từ nút nguồn đến vị trí đích
        scale = max(0.05, eased_p)
        draw_w = max(1, round(rect.w * scale))
        draw_h = max(1, round(rect.h * scale))
        scaled_menu = pygame.transform.smoothscale(panel_surf, (draw_w, draw_h))
        scaled_menu.set_alpha(round(255 * eased_p))

        dest_cx = rect.centerx
        dest_cy = rect.centery
        curr_cx = self.animation_origin[0] + (dest_cx - self.animation_origin[0]) * eased_p
        curr_cy = self.animation_origin[1] + (dest_cy - self.animation_origin[1]) * eased_p

        surface.blit(scaled_menu, (round(curr_cx - draw_w / 2), round(curr_cy - draw_h / 2)))

    def _get_icon_surface(
        self, icon_name: str, target_size: int, color: Tuple[int, int, int]
    ) -> Optional[pygame.Surface]:
        rgb = (int(color[0]), int(color[1]), int(color[2]))
        cache_key = (icon_name, target_size, rgb)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        file_candidates = self.ICON_MAP.get(icon_name, [f"{icon_name}.svg", f"{icon_name}.png"])
        found_path = None
        for filename in file_candidates:
            p = self.ICON_DIR / filename
            if p.exists():
                found_path = p
                break

        if not found_path:
            return None

        try:
            raw_img = pygame.image.load(str(found_path))
            w, h = raw_img.get_size()
            if w <= 0 or h <= 0:
                return None
            scale = target_size / max(w, h)
            nw = max(1, round(w * scale))
            nh = max(1, round(h * scale))
            scaled = pygame.transform.smoothscale(raw_img, (nw, nh))

            tinted = scaled.copy()
            tinted.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
            tinted.fill((*rgb, 255), special_flags=pygame.BLEND_RGBA_MULT)

            self._icon_cache[cache_key] = tinted
            return tinted
        except Exception as e:
            print(f"[AssistiveTouch] Lỗi nạp icon {icon_name} ({found_path}): {e}")
            return None

    def _draw_icon(
        self,
        surface: pygame.Surface,
        icon_type: str,
        cx: int,
        cy: int,
        color,
        target_size: int = 28,
    ):
        """Vẽ icon từ assets/icon (SVG/PNG) hoặc fallback vector."""
        icon_surf = self._get_icon_surface(icon_type, target_size, color)
        if icon_surf:
            rect = icon_surf.get_rect(center=(cx, cy))
            surface.blit(icon_surf, rect)
        else:
            self._draw_vector_fallback(surface, icon_type, cx, cy, color)

    def _draw_vector_fallback(self, surface: pygame.Surface, icon_type: str, cx: int, cy: int, color):
        """Fallback vẽ vector nếu không tìm thấy tệp icon."""
        if icon_type in ("home", "trang_chu"):
            pygame.draw.polygon(surface, color, [(cx, cy - 9), (cx - 10, cy - 1), (cx + 10, cy - 1)])
            pygame.draw.rect(surface, color, (cx - 8, cy - 1, 16, 11), border_radius=1)
            pygame.draw.rect(surface, (232, 237, 240), (cx - 3, cy + 2, 6, 8))
        elif icon_type == "wifi":
            pygame.draw.circle(surface, color, (cx, cy + 6), 2)
            pygame.draw.arc(surface, color, (cx - 8, cy, 16, 12), 0.78, 2.36, 2)
            pygame.draw.arc(surface, color, (cx - 14, cy - 6, 28, 20), 0.78, 2.36, 2)
        elif icon_type in ("persona", "config"):
            pygame.draw.circle(surface, color, (cx, cy - 5), 5)
            pygame.draw.arc(surface, color, (cx - 9, cy, 18, 14), 0.2, 2.94, 2)
            pygame.draw.line(surface, color, (cx - 8, cy + 7), (cx + 8, cy + 7), 2)
        elif icon_type in ("faces", "face"):
            pygame.draw.circle(surface, color, (cx, cy), 10, 2)
            pygame.draw.circle(surface, color, (cx - 3, cy - 2), 1)
            pygame.draw.circle(surface, color, (cx + 3, cy - 2), 1)
            pygame.draw.arc(surface, color, (cx - 5, cy - 2, 10, 7), 3.14, 0, 2)
        elif icon_type == "system":
            pygame.draw.circle(surface, color, (cx, cy), 8, 2)
            pygame.draw.circle(surface, color, (cx, cy), 3)
            for i in range(4):
                angle = i * (math.pi / 4)
                dx, dy = int(round(10 * math.cos(angle))), int(round(10 * math.sin(angle)))
                pygame.draw.line(surface, color, (cx - dx, cy - dy), (cx + dx, cy + dy), 2)
        elif icon_type in ("close", "exit"):
            pygame.draw.line(surface, color, (cx - 7, cy - 7), (cx + 7, cy + 7), 2)
            pygame.draw.line(surface, color, (cx - 7, cy + 7), (cx + 7, cy - 7), 2)

if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 480))
    clock = pygame.time.Clock()
    assistive_touch = AssistiveTouch(screen_size=(800, 480))

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            assistive_touch.handle_event(event)

        assistive_touch.update()

        screen.fill((205, 214, 224))
        assistive_touch.draw(screen)
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()