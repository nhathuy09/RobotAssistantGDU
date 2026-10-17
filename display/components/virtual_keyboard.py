import pygame
from typing import Callable, List, Optional, Tuple
from display.components.base_widget import BaseWidget
from display.theme import Colors


class VirtualKeyboard(BaseWidget):
    """Component bàn phím ảo cảm ứng (On-Screen Keyboard)."""

    def __init__(
        self,
        top_y: int = 220,
        height: int = 260,
        width: int = 800,
        on_submit: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(pygame.Rect(0, top_y, width, height))
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.active_input = None

        self.is_numeric = False
        self.is_shift = False
        self.font = pygame.font.SysFont("Segoe UI", 16, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 13)

        self._key_rects: List[Tuple[pygame.Rect, str, str]] = []  # (rect, key_code, label)
        self.visible = False

    def open(self, target_input=None):
        self.active_input = target_input
        self.visible = True
        self.is_shift = False
        self.is_numeric = False

    def close(self):
        self.visible = False
        if self.active_input is not None:
            self.active_input.set_focus(False)
        self.active_input = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for r, code, _ in self._key_rects:
                if r.collidepoint(event.pos):
                    self._on_press_key(code)
                    return True
            # Nếu chạm vào vùng bàn phím nhưng không trúng phím nào
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def _on_press_key(self, code: str):
        target=self.active_input
        if code == "cancel":
            self.close()
            if self.on_cancel:
                self.on_cancel()
            return
        elif code == "submit":
            if target is not None and target.on_submit:
                target.on_submit(target.value)
            if self.on_submit:
                self.on_submit()
            return
        elif code == "shift":
            self.is_shift = not self.is_shift
            return
        elif code == "123":
            self.is_numeric = not self.is_numeric
            self.is_shift = False
        elif code == "back":
            if target.value:
                target.value=target.value[:-1]
                if target.on_text_change:
                    target.on_text_change(target.value)
            return
        if code == "space":
            new_text=""
        else:
            new_text = code.upper() if self.is_shift else code
        if target.is_numeric:
            new_text = "".join(c for c in new_text if c.isdigit())
        if not new_text:
            return
        if target.max_length is not None:
            remaining= target.maxlength - len(target.value)
            if remaining <= 0:
                return
            new_text = new_text[:remaining]
        target.value += new_text
        if target.on_text_change:
            target.on_text_change(target.value)
        if self.is_shift or code not in("space",):
            self.is_shift = False
    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        self._key_rects.clear()
        mouse_pos = pygame.mouse.get_pos()

        # Nền bàn phím
        pygame.draw.rect(surface, (235, 240, 246), self.rect)
        pygame.draw.line(surface, Colors.CARD_BORDER, (0, self.rect.y), (self.rect.w, self.rect.y), 1)

        if self.is_numeric:
            rows = [
                ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
                ["-", "/", ":", ";", "(", ")", "$", "&", "@", '"'],
                ["shift", ".", ",", "?", "!", "'", "#", "back"],
            ]
        else:
            rows = [
                ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
                ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
                ["shift", "z", "x", "c", "v", "b", "n", "m", "back"],
            ]

        key_h = 44
        key_gap = 5
        curr_y = self.rect.y + 10

        for row in rows:
            key_w = 60
            widths = [86 if k in ("shift", "back") else key_w for k in row]
            total_w = sum(widths) + key_gap * (len(row) - 1)
            curr_x = (self.rect.w - total_w) // 2

            for k, w in zip(row, widths):
                kr = pygame.Rect(curr_x, curr_y, w, key_h)
                label = k.upper() if (self.is_shift and len(k) == 1) else k
                if k == "shift":
                    label = "CAPS"
                elif k == "back":
                    label = "DEL"
                self._draw_key(surface, kr, k, label, mouse_pos)
                curr_x += w + key_gap
            curr_y += key_h + key_gap

        # Hàng phím dưới cùng: ?123, space, Hủy, Xác nhận
        sym_w, space_w, cancel_w, submit_w = 78, 300, 100, 130
        total_bot = sym_w + space_w + cancel_w + submit_w + key_gap * 3
        curr_x = (self.rect.w - total_bot) // 2

        # ?123
        r_sym = pygame.Rect(curr_x, curr_y, sym_w, key_h)
        self._draw_key(surface, r_sym, "123", "ABC" if self.is_numeric else "?123", mouse_pos)
        curr_x += sym_w + key_gap

        # Space
        r_sp = pygame.Rect(curr_x, curr_y, space_w, key_h)
        self._draw_key(surface, r_sp, "space", "khoảng trắng", mouse_pos)
        curr_x += space_w + key_gap

        # Cancel
        r_can = pygame.Rect(curr_x, curr_y, cancel_w, key_h)
        self._draw_key(surface, r_can, "cancel", "Hủy", mouse_pos, fg=Colors.COLOR_DANGER)
        curr_x += cancel_w + key_gap

        # Submit
        r_sub = pygame.Rect(curr_x, curr_y, submit_w, key_h)
        self._draw_key(
            surface,
            r_sub,
            "submit",
            "Xong",
            mouse_pos,
            bg=Colors.BTN_PRIMARY,
            fg=Colors.COLOR_WHITE,
        )

    def _draw_key(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        code: str,
        label: str,
        mouse_pos: Tuple[int, int],
        bg=None,
        fg=None,
    ):
        hovered = rect.collidepoint(mouse_pos)
        fill = bg or ((245, 248, 255) if hovered else Colors.COLOR_WHITE)
        text_col = fg or Colors.TEXT_DARK

        if code == "shift" and self.is_shift:
            fill = (220, 235, 255)

        pygame.draw.rect(surface, fill, rect, border_radius=8)
        border_col = (180, 200, 225) if hovered else Colors.CARD_BORDER
        pygame.draw.rect(surface, border_col, rect, 1, border_radius=8)

        use_font = self.font_small if len(label) > 2 else self.font
        ts = use_font.render(label, True, text_col)
        surface.blit(ts, ts.get_rect(center=rect.center))

        self._key_rects.append((rect, code, label))
