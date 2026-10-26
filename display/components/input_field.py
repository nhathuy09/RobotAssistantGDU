
import pygame
from typing import Callable, Optional

from .base_widget import BaseWidget
from ..theme import Colors, Theme

class InputField(BaseWidget):
    def __init__(
        self,
        rect: pygame.Rect,
        theme: Theme,
        placeholder: Optional[str] = None,
        text: Optional[str] = None,
        visible: bool = True,
        enabled: bool = True,
        font: Optional[pygame.font.Font] = None,
        is_password: bool = False,
        has_eye_toggle: bool = False,
        max_length: Optional[int] = None,
        is_numeric: bool = False,
        on_text_change: Optional[Callable[[str], None]] = None,
        on_submit: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(rect, visible, enabled)

        self.theme = theme
        self.placeholder = placeholder or ""
        self.value = text or ""

        self.font = font or theme.get_font(14)
        self.bg_color = Colors.INPUT_BG
        self.border_color = Colors.INPUT_BORDER
        self.focus_color = Colors.INPUT_BORDER_FOCUS
        self.text_color = Colors.TEXT_DARK
        self.placeholder_color = Colors.TEXT_MUTED

        self.is_password = is_password
        self.has_eye_toggle = has_eye_toggle
        self.show_password = False
        self.max_length = max_length
        self.is_numeric = is_numeric

        self.on_text_change = on_text_change
        self.on_submit = on_submit

        self.padding = 14
        self.border_radius = 12

        # Áp dụng quy tắc nhập liệu cho nội dung ban đầu.
        if self.is_numeric:
            self.value = "".join(c for c in self.value if c.isdigit())
        if self.max_length is not None:
            self.value = self.value[:self.max_length]

    @property
    def eye_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.right - 44, self.rect.y, 44, self.rect.height)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.has_eye_toggle and self.eye_rect.collidepoint(event.pos):
                if self.is_password:
                    self.show_password = not self.show_password
                    self.focused = True
                return True
            clicked = self.rect.collidepoint(event.pos)
            self.set_focus(clicked)
            return clicked
        if not self.focused:
            return False
        if event.type == pygame.TEXTINPUT:
            new_text = event.text
            if self.is_numeric:
                new_text = "".join(c for c in new_text if c.isdigit())
            if not new_text:
                return False
            if self.max_length is not None:
                remaining = self.max_length - len(self.value)
                if remaining <= 0:
                    return True
                new_text = new_text[:remaining]
            self.value += new_text
            if self.on_text_change:
                self.on_text_change(self.value)
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.value:
                    self.value = self.value[:-1]

                    if self.on_text_change:
                        self.on_text_change(self.value)

                return True

            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.on_submit:
                    self.on_submit(self.value)
                return True
        return False

    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return
        border = self.focus_color if self.focused else self.border_color
        border_width = 2 if self.focused else 1
        pygame.draw.rect(surface,self.bg_color,self.rect, border_radius=self.border_radius,)
        pygame.draw.rect(surface,border,self.rect,width=border_width,border_radius=self.border_radius,)

        if self.value:
            if self.is_password and not self.show_password:
                display_text = "*" * len(self.value)
            else:
                display_text = self.value
            text_color = self.text_color
        else:
            display_text = self.placeholder
            text_color = self.placeholder_color
        text_surface = self.font.render(display_text, True, text_color)
        # Vùng hiển thị văn bản, chừa chỗ cho icon con mắt.
        left = self.rect.x + self.padding
        right = self.rect.right - self.padding
        if self.has_eye_toggle:
            right = self.eye_rect.left
        text_area = pygame.Rect(left, self.rect.y + 2,max(0, right - left), self.rect.height - 4,)
        # Cắt phần chữ tràn ra ngoài vùng nhập liệu.
        old_clip = surface.get_clip()
        surface.set_clip(text_area)
        text_rect = text_surface.get_rect( midleft=(left, self.rect.centery))
        surface.blit(text_surface, text_rect)

        # Con trỏ nhập liệu.
        if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            cursor_x = min(text_rect.right + 2, text_area.right - 1)
            cursor_y1 = self.rect.centery - 8
            cursor_y2 = self.rect.centery + 8

            if text_area.width > 0:
                pygame.draw.line(surface,self.text_color,(cursor_x, cursor_y1),(cursor_x, cursor_y2),2,)
        surface.set_clip(old_clip)

        if self.has_eye_toggle and self.is_password:
            self._draw_eye(surface, self.eye_rect.centerx, self.eye_rect.centery, self.show_password)

    def _draw_eye(self, surface: pygame.Surface, cx: int, cy: int, showing: bool):
        color = Colors.PINE_GREEN if showing else Colors.SAGE_MUTED

        # Vẽ hình dáng mắt mềm mại
        eye_rect = pygame.Rect(cx - 11, cy - 6, 22, 13)
        pygame.draw.ellipse(surface, color, eye_rect, width=2)
        pygame.draw.circle(surface, color, (cx, cy), 3)

        if not showing:
            # Gạch chéo mảnh tinh tế cho trạng thái ẩn mật khẩu
            pygame.draw.line(surface, color, (cx - 9, cy + 6), (cx + 9, cy - 6), 2)
