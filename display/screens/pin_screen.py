import pygame
from typing import Optional, Dict
import hashlib
from display.screens.base_screen import BaseScreen
from display.theme import Colors, Theme
from database.repositories import AdminRepository, SystemLogRepository

class PinScreen(BaseScreen):
    """Màn hình bảo mật nhập mã PIN khi truy cập các tính năng cấu hình quan trọng."""

    PAGE_BG = Colors.PAGE_BG
    CARD_BG = Colors.CARD_BG
    CARD_BORDER = Colors.CARD_BORDER
    KEY_BG = Colors.KEY_BG
    KEY_BG_HOVER = Colors.KEY_BG_HOVER
    KEY_BORDER = Colors.KEY_BORDER
    TEXT_MAIN = Colors.TEXT_MAIN
    TEXT_MUTED = Colors.TEXT_MUTED
    ACCENT_COLOR = Colors.PINE_GREEN
    SUCCESS_COLOR = Colors.SUCCESS_COLOR
    ERROR_COLOR = Colors.ERROR_COLOR

    SCREEN_TITLES: Dict[str, str] = {
        "wifi": "Wi-Fi Settings",
        "persona": "Personality Configuration",
        "system": "System Settings",
        "faces_gallery": "Face Expressions Gallery",
    }

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.target_screen: str = "face"
        self.target_kwargs: dict = {}
        self.pin_value: str = ""
        self.message: str = ""
        self.is_success: bool = False
        self.success_timer: int = 0

        # Card trung tâm 380x430 px
        self.card_rect = pygame.Rect(210, 25, 380, 430)

        # Xây dựng các phím bấm keypad (4 hàng x 3 cột)
        self.keys = []
        key_w, key_h = 76, 46
        gap_x, gap_y = 12, 10
        start_x = self.card_rect.x + (self.card_rect.width - (key_w * 3 + gap_x * 2)) // 2
        start_y = self.card_rect.y + 155

        layout = [
            [("1", "1"), ("2", "2"), ("3", "3")],
            [("4", "4"), ("5", "5"), ("6", "6")],
            [("7", "7"), ("8", "8"), ("9", "9")],
            [("cancel", "Hủy"), ("0", "0"), ("back", "DEL")],
        ]

        for r_idx, row in enumerate(layout):
            for c_idx, (code, label) in enumerate(row):
                kx = start_x + c_idx * (key_w + gap_x)
                ky = start_y + r_idx * (key_h + gap_y)
                rect = pygame.Rect(kx, ky, key_w, key_h)
                self.keys.append({"code": code, "label": label, "rect": rect})

    def on_enter(self, target_screen: str = "face", **kwargs):
        self.target_screen = target_screen
        self.target_kwargs = kwargs
        self.pin_value = ""
        self.message = ""
        self.is_success = False
        self.success_timer = 0

    def on_leave(self):
        self.pin_value = ""
        self.message = ""

    @staticmethod
    def _hash_value(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _verify_pin(self):
        if len(self.pin_value) != 6:
            self.message = f"Mã PIN bắt buộc phải đúng 6 chữ số ({len(self.pin_value)}/6)."
            return

        if AdminRepository.verify_pin(self.pin_value):
            self.is_success = True
            self.message = "Mở khóa thành công!"
            self.success_timer = pygame.time.get_ticks()
            SystemLogRepository.log("OK", "PIN", f"Mở khóa mã PIN thành công cho màn hình '{self.target_screen}'.")
        else:
            self.message = "Mã PIN không đúng, vui lòng thử lại."
            self.pin_value = ""
            SystemLogRepository.log("WARN", "PIN", f"Nhập sai mã PIN khi truy cập '{self.target_screen}'.")

    def _on_key_press(self, code: str):
        if self.is_success:
            return

        self.message = ""
        if code == "cancel":
            # Quay lại màn hình chính face
            self.app_manager.switch_screen("face")
        elif code == "back":
            if self.pin_value:
                self.pin_value = self.pin_value[:-1]
        elif code.isdigit():
            if len(self.pin_value) < 6:
                self.pin_value += code
                # Tự động kiểm tra ngay khi nhập đủ 6 chữ số
                if len(self.pin_value) == 6:
                    self._verify_pin()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.is_success:
            return True

        # Hỗ trợ bàn phím vật lý
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._on_key_press("cancel")
                return True
            elif event.key == pygame.K_BACKSPACE:
                self._on_key_press("back")
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if len(self.pin_value) == 6:
                    self._verify_pin()
                return True
            elif event.unicode and event.unicode.isdigit():
                self._on_key_press(event.unicode)
                return True

        # Hỗ trợ chạm / click chuột vào các phím
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key in self.keys:
                if key["rect"].collidepoint(event.pos):
                    self._on_key_press(key["code"])
                    return True

            # Chạm bên ngoài card -> Hủy và quay về trang chủ
            if not self.card_rect.collidepoint(event.pos):
                self._on_key_press("cancel")
                return True

        return False

    def update(self):
        # Sau khi xác thực thành công, chờ 120ms rồi chuyển sang trang đích
        if self.is_success and self.success_timer > 0:
            if pygame.time.get_ticks() - self.success_timer > 120:
                self.app_manager.switch_screen(
                    self.target_screen,
                    pin_verified=True,
                    **self.target_kwargs,
                )

    def _draw_lock_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng ổ khóa an toàn vector."""
        body_rect = pygame.Rect(cx - 7, cy - 3, 14, 12)
        pygame.draw.rect(surface, color, body_rect, width=2, border_radius=3)
        pygame.draw.arc(surface, color, (cx - 5, cy - 10, 10, 10), 0, 3.14159, 2)
        pygame.draw.line(surface, color, (cx - 5, cy - 5), (cx - 5, cy - 3), 2)
        pygame.draw.line(surface, color, (cx + 5, cy - 5), (cx + 5, cy - 3), 2)
        pygame.draw.circle(surface, color, (cx, cy + 2), 2)

    def draw(self, surface: pygame.Surface):
        # 1. Nền toàn màn hình
        surface.fill(self.PAGE_BG)

        # 2. Card trắng ở trung tâm
        pygame.draw.rect(surface, self.CARD_BG, self.card_rect, border_radius=24)
        pygame.draw.rect(surface, self.CARD_BORDER, self.card_rect, width=1, border_radius=24)

        cx = self.card_rect.centerx
        top = self.card_rect.y

        # 3. Header: Icon ổ khóa
        lock_col = self.SUCCESS_COLOR if self.is_success else self.ACCENT_COLOR
        self._draw_lock_icon(surface, cx, top + 30, lock_col)

        # Tiêu đề & Phụ đề trang cần mở khóa
        title_surf = self.theme.get_font(21, bold=True).render("Security PIN", True, self.TEXT_MAIN)
        surface.blit(title_surf, (cx - title_surf.get_width() // 2, top + 48))

        sub_label = f"{self.SCREEN_TITLES.get(self.target_screen, 'Protected Access')} • 6 chữ số"
        sub_surf = self.theme.get_font(12).render(sub_label, True, self.TEXT_MUTED)
        surface.blit(sub_surf, (cx - sub_surf.get_width() // 2, top + 76))

        # 4. Hiển thị PIN dots (các chấm tròn biểu thị số ký tự đã nhập)
        dot_count = 6
        dot_radius = 6
        dot_gap = 14
        total_dots_w = dot_count * (dot_radius * 2) + (dot_count - 1) * dot_gap
        dot_start_x = cx - total_dots_w // 2 + dot_radius
        dot_y = top + 108

        for i in range(dot_count):
            dot_cx = dot_start_x + i * (dot_radius * 2 + dot_gap)
            if i < len(self.pin_value):
                fill_color = self.SUCCESS_COLOR if self.is_success else self.ACCENT_COLOR
                pygame.draw.circle(surface, fill_color, (dot_cx, dot_y), dot_radius)
            else:
                pygame.draw.circle(surface, (215, 210, 202), (dot_cx, dot_y), dot_radius, 2)

        # 5. Thông báo lỗi hoặc thành công
        if self.message:
            msg_color = self.SUCCESS_COLOR if self.is_success else self.ERROR_COLOR
            msg_surf = self.theme.get_font(12, bold=True).render(self.message, True, msg_color)
            surface.blit(msg_surf, (cx - msg_surf.get_width() // 2, top + 128))

        # 6. Bàn phím số Keypad
        mouse_pos = pygame.mouse.get_pos()
        for key in self.keys:
            r = key["rect"]
            hovered = r.collidepoint(mouse_pos)
            bg = self.KEY_BG_HOVER if hovered else self.KEY_BG

            if key["code"] == "cancel":
                fg = self.ERROR_COLOR
                font = self.theme.get_font(14, bold=True)
            elif key["code"] == "back":
                fg = self.TEXT_MUTED
                font = self.theme.get_font(14, bold=True)
            else:
                fg = self.TEXT_MAIN
                font = self.theme.get_font(18, bold=True)

            pygame.draw.rect(surface, bg, r, border_radius=12)
            pygame.draw.rect(surface, self.KEY_BORDER, r, width=1, border_radius=12)

            ts = font.render(key["label"], True, fg)
            surface.blit(ts, ts.get_rect(center=r.center))
