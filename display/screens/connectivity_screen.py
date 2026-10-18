import math
import time
import pygame
from display.screens.base_screen import BaseScreen
from display.theme import Colors
from display.components.virtual_keyboard import VirtualKeyboard
from display.components.input_field import InputField


class ConnectivityScreen(BaseScreen):
    """Màn hình cấu hình Wi-Fi & Kết nối mạng."""

    MARGIN = 28
    ROW_H = 56
    ROW_GAP = 8

    # Fallbacks cho theme.py nếu chưa khai báo các màu riêng của menu.
    MENU_SLATE = getattr(Colors, "MENU_SLATE", Colors.COLOR_62798C)
    COLOR_WHITE = getattr(Colors, "COLOR_WHITE", Colors.COLOR_TEETH)

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.wifi = app_manager.wifi

        self.status_rect = pygame.Rect(self.MARGIN, 96, 800 - 2 * self.MARGIN, 112)
        self.section_y = 224
        self.list_top = 282
        self.list_rect = pygame.Rect(self.MARGIN, self.list_top, 800 - 2 * self.MARGIN, 480 - 10 - self.list_top)

        self.back_btn_rect = pygame.Rect(28, 14, 134, 48)

        self.scroll_y = 0
        self.is_dragging_list = False
        self.drag_start_y = 0
        self.drag_start_scroll = 0
        self.pending_row = None

        self.last_networks = []
        self.row_rects = []
        self.scan_btn_rect = pygame.Rect(800 - self.MARGIN - 174, self.section_y, 174, 48)
        self.forget_btn_rect = pygame.Rect(0, 0, 0, 0)

        # Bàn phím ảo nhập mật khẩu
        self.keyboard = VirtualKeyboard(
            top_y=220,
            on_submit=self._on_submit_password,
            on_cancel=self._on_cancel_password,
        )
        self.pw_input = InputField(
            rect=pygame.Rect(self.MARGIN + 90, 160, 800 - 2 * self.MARGIN - 180, 48),
            theme=self.theme,
            placeholder="Nhập mật khẩu Wi-Fi...",
            font=self.theme.font_body,
            is_password=True,
            has_eye_toggle=True,
        )
        self.keyboard.active_input = self.pw_input
        self.pending_ssid = ""

    def on_enter(self, **kwargs):
        self.scroll_y = 0
        self.is_dragging_list = False
        self.pending_row = None
        self.keyboard.close()
        self.pending_ssid = ""
        try:
            self.wifi.scan(force=True)
        except Exception as exc:
            # Lỗi sẽ được hiển thị nếu wifi.snapshot() đưa lỗi ra trạng thái.
            print(f"[Wi-Fi] Không thể bắt đầu quét mạng: {exc}")

    def _on_submit_password(self, *_args):
        if not self.pending_ssid:
            self.keyboard.close()
            return
        try:
            self.wifi.connect(self.pending_ssid, self.pw_input.value)
        except Exception as exc:
            print(f"[Wi-Fi] Không thể kết nối {self.pending_ssid}: {exc}")
        finally:
            self.keyboard.close()

    def _on_cancel_password(self, *_args):
        self.keyboard.close()
        self.pending_ssid = ""

    def handle_event(self, event: pygame.event.Event) -> bool:
        # Khi bàn phím ảo mở, chỉ xử lý ô nhập mật khẩu và bàn phím.
        if self.keyboard.visible:
            if self.pw_input.handle_event(event):
                return True
            if self.keyboard.handle_event(event):
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[1] < 200:
                    self.keyboard.close()
                    self.pending_ssid = ""
                    return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn_rect.collidepoint(event.pos):
                self.app_manager.switch_screen("face")
                return True

            if self.forget_btn_rect.collidepoint(event.pos):
                try:
                    snap = self.wifi.snapshot()
                    ssid = snap.get("status", {}).get("ssid")
                    if ssid:
                        self.wifi.forget(ssid)
                except Exception as exc:
                    print(f"[Wi-Fi] Không thể quên mạng: {exc}")
                return True

            if self.scan_btn_rect.collidepoint(event.pos):
                try:
                    self.wifi.scan(force=True)
                except Exception as exc:
                    print(f"[Wi-Fi] Không thể quét mạng: {exc}")
                return True

            # Chỉ bắt đầu chọn/kéo khi nhấn bên trong vùng danh sách.
            if self.list_rect.collidepoint(event.pos):
                for rect, row in self.row_rects:
                    if rect.colliderect(self.list_rect) and rect.collidepoint(event.pos):
                        self.pending_row = row
                        self.drag_start_y = event.pos[1]
                        self.drag_start_scroll = self.scroll_y
                        self.is_dragging_list = False
                        return True

                self.pending_row = None
                self.drag_start_y = event.pos[1]
                self.drag_start_scroll = self.scroll_y
                self.is_dragging_list = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[0] and (
                self.pending_row is not None or self.list_rect.collidepoint(event.pos)
            ):
                dy = event.pos[1] - self.drag_start_y
                if abs(dy) > 6:
                    self.is_dragging_list = True
                    self.pending_row = None
                    total_h = (
                        len(self.last_networks) * self.ROW_H
                        + max(0, len(self.last_networks) - 1) * self.ROW_GAP
                    )
                    max_scroll = max(0, total_h - self.list_rect.height)
                    self.scroll_y = max(0, min(self.drag_start_scroll - dy, max_scroll))
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pending_row is not None and not self.is_dragging_list:
                row = self.pending_row
                self.pending_row = None
                self._activate_row(row)
                return True
            was_dragging = self.is_dragging_list
            self.pending_row = None
            self.is_dragging_list = False
            return was_dragging

        elif event.type == pygame.MOUSEWHEEL:
            if self.list_rect.collidepoint(pygame.mouse.get_pos()):
                total_h = (
                    len(self.last_networks) * self.ROW_H
                    + max(0, len(self.last_networks) - 1) * self.ROW_GAP
                )
                max_scroll = max(0, total_h - self.list_rect.height)
                self.scroll_y = max(0, min(self.scroll_y - event.y * 42, max_scroll))
                return True

        return False

    def _activate_row(self, row):
        ssid = row.get("ssid", "")
        if not ssid or row.get("in_use"):
            return

        try:
            if row.get("saved") and row.get("secure"):
                self.wifi.connect(ssid, None)
            elif not row.get("secure"):
                self.wifi.connect(ssid, "")
            else:
                self.pending_ssid = ssid
                self.pw_input.value = ""
                self.pw_input.show_password = False
                self.pw_input.placeholder = f"Nhập mật khẩu cho {ssid}..."
                self.pw_input.set_focus(True)
                self.keyboard.open(self.pw_input)
        except Exception as exc:
            print(f"[Wi-Fi] Không thể xử lý mạng {ssid}: {exc}")

    def update(self):
        self.keyboard.update()
        self.pw_input.update()

    def draw(self, surface: pygame.Surface):
        surface.fill(Colors.BG_PAGE)
        try:
            snap = self.wifi.snapshot()
        except Exception as exc:
            print(f"[Wi-Fi] Không đọc được trạng thái mạng: {exc}")
            snap = {
                "status": {"connected": False, "ssid": "", "ip": "", "signal": 0},
                "networks": [],
                "scanning": False,
                "error": "Không đọc được trạng thái Wi-Fi",
                "result": ("", False, 0),
            }
        mouse_pos = pygame.mouse.get_pos()

        # Header: Nút Quay lại & Tiêu đề
        self._draw_header(surface, mouse_pos)

        # Khung trạng thái mạng hiện tại
        self._draw_status(surface, snap, mouse_pos)

        if self.keyboard.visible:
            # Hiện ô nhập mật khẩu và bàn phím ảo
            self._draw_password_panel(surface)
            self.keyboard.draw(surface)
        else:
            # Danh sách mạng có sẵn
            self._draw_section(surface, snap, mouse_pos)
            self._draw_list(surface, snap, mouse_pos)

        # Toast thông báo kết quả
        self._draw_toast(surface, snap)

    def _draw_header(self, surface: pygame.Surface, mouse_pos):
        hover_back = self.back_btn_rect.collidepoint(mouse_pos)
        bg = (248, 246, 240) if hover_back else Colors.CARD_BG
        pygame.draw.rect(surface, bg, self.back_btn_rect, border_radius=14)
        pygame.draw.rect(surface, Colors.CARD_BORDER, self.back_btn_rect, 1, border_radius=14)

        # Mũi tên quay lại
        ay = self.back_btn_rect.centery
        ax = self.back_btn_rect.x + 24
        pygame.draw.line(surface, self.MENU_SLATE, (ax, ay), (ax + 16, ay), 3)
        pygame.draw.line(surface, self.MENU_SLATE, (ax, ay), (ax + 7, ay - 6), 3)
        pygame.draw.line(surface, self.MENU_SLATE, (ax, ay), (ax + 7, ay + 6), 3)

        ts = self.theme.font_body_bold.render("Quay lại", True, self.MENU_SLATE)
        surface.blit(ts, (ax + 24, ay - ts.get_height() // 2))

        title = self.theme.font_h1.render("Wi-Fi & Cài đặt Mạng", True, Colors.TEXT_DARK)
        surface.blit(title, (self.back_btn_rect.right + 20, ay - title.get_height() // 2))

    def _draw_status(self, surface: pygame.Surface, snap, mouse_pos):
        r = self.status_rect
        st = snap["status"]

        bg = Colors.GREEN_BG if st["connected"] else Colors.CARD_BG
        border = Colors.GREEN_BORDER if st["connected"] else Colors.CARD_BORDER

        pygame.draw.rect(surface, bg, r, border_radius=16)
        pygame.draw.rect(surface, border, r, 1, border_radius=16)

        # Hộp icon tín hiệu
        ib = pygame.Rect(r.x + 16, r.y + (r.h - 56) // 2, 56, 56)
        pygame.draw.rect(surface, (223, 231, 224), ib, border_radius=14)
        self._draw_signal_bars(surface, ib, Colors.GREEN_ICON if st["connected"] else Colors.TEXT_MUTED, st["signal"])

        tx = ib.right + 18
        if st["connected"]:
            surface.blit(self.theme.font_small.render("Mạng đang kết nối", True, Colors.TEXT_MUTED), (tx, r.y + 22))
            surface.blit(self.theme.font_title.render(st["ssid"], True, Colors.TEXT_DARK), (tx, r.y + 44))
            sub = f"IP nội bộ: {st['ip'] or '...'}  •  Tín hiệu: {st['signal']}%"
            surface.blit(self.theme.font_small.render(sub, True, Colors.TEXT_MUTED), (tx, r.y + 72))

            # Nút Quên mạng
            fw, fh = 96, 44
            fx = r.right - fw - 16
            self.forget_btn_rect = pygame.Rect(fx, r.centery - fh // 2, fw, fh)
            hov_f = self.forget_btn_rect.collidepoint(mouse_pos)
            pygame.draw.rect(surface, Colors.CARD_BG, self.forget_btn_rect, border_radius=10)
            pygame.draw.rect(surface, Colors.CARD_BORDER, self.forget_btn_rect, 1, border_radius=10)
            fg = Colors.COLOR_DANGER if hov_f else self.MENU_SLATE
            f_ts = self.theme.font_body_bold.render("Quên mạng", True, fg)
            surface.blit(f_ts, f_ts.get_rect(center=self.forget_btn_rect.center))
        else:
            surface.blit(self.theme.font_small.render("Trạng thái kết nối", True, Colors.TEXT_MUTED), (tx, r.y + 22))
            surface.blit(self.theme.font_title.render("Chưa kết nối Wi-Fi", True, Colors.TEXT_DARK), (tx, r.y + 44))
            err_msg = snap["error"] or "Chọn một mạng bên dưới để kết nối"
            surface.blit(self.theme.font_small.render(err_msg, True, Colors.TEXT_MUTED), (tx, r.y + 72))
            self.forget_btn_rect = pygame.Rect(0, 0, 0, 0)

    def _draw_section(self, surface: pygame.Surface, snap, mouse_pos):
        y = self.section_y
        title = self.theme.font_title.render("Mạng khả dụng lân cận", True, Colors.TEXT_DARK)
        surface.blit(title, (self.MARGIN, y + 14))

        count = len(snap["networks"])
        cnt = self.theme.font_small.render(f"({count} mạng)", True, Colors.TEXT_MUTED)
        surface.blit(cnt, (self.MARGIN + title.get_width() + 8, y + 16))

        # Nút Quét mạng
        hov = self.scan_btn_rect.collidepoint(mouse_pos)
        pygame.draw.rect(surface, (248, 246, 240) if hov else Colors.CARD_BG, self.scan_btn_rect, border_radius=14)
        pygame.draw.rect(surface, Colors.CARD_BORDER, self.scan_btn_rect, 1, border_radius=14)

        scan_label = "Đang quét..." if snap["scanning"] else "Quét / Làm mới"
        ts = self.theme.font_body_bold.render(scan_label, True, self.MENU_SLATE)
        surface.blit(ts, ts.get_rect(center=self.scan_btn_rect.center))

    def _draw_list(self, surface: pygame.Surface, snap, mouse_pos):
        nets = snap["networks"]
        self.last_networks = nets
        self.row_rects.clear()

        content_h = len(nets) * self.ROW_H + max(0, len(nets) - 1) * self.ROW_GAP
        max_s = max(0, content_h - self.list_rect.height)
        self.scroll_y = max(0, min(self.scroll_y, max_s))

        if not nets:
            msg = "Đang tìm kiếm mạng..." if snap["scanning"] else (snap["error"] or "Không tìm thấy mạng Wi-Fi nào")
            ts = self.theme.font_body.render(msg, True, Colors.TEXT_MUTED)
            surface.blit(ts, ts.get_rect(center=(400, self.list_rect.centery)))
            return

        old_clip = surface.get_clip()
        surface.set_clip(self.list_rect)

        for idx, row in enumerate(nets):
            ry = self.list_top + idx * (self.ROW_H + self.ROW_GAP) - self.scroll_y
            rect = pygame.Rect(self.MARGIN, ry, 800 - 2 * self.MARGIN, self.ROW_H)
            self.row_rects.append((rect, row))
            if not rect.colliderect(self.list_rect):
                continue

            in_use = row.get("in_use", False)
            hovered = rect.collidepoint(mouse_pos)
            bg = Colors.GREEN_BG if in_use else ((250, 248, 244) if hovered else Colors.CARD_BG)
            border = Colors.GREEN_BORDER if in_use else Colors.CARD_BORDER

            pygame.draw.rect(surface, bg, rect, border_radius=14)
            pygame.draw.rect(surface, border, rect, 1, border_radius=14)

            # Icon vạch sóng
            icon_box = pygame.Rect(rect.x + 14, rect.centery - 18, 36, 36)
            pygame.draw.rect(surface, (240, 240, 235), icon_box, border_radius=10)
            self._draw_signal_bars(surface, icon_box, self.MENU_SLATE, row.get("signal", 0))

            # Tên SSID
            tx = icon_box.right + 12
            ssid_ts = self.theme.font_body_bold.render(row["ssid"], True, Colors.TEXT_DARK)
            surface.blit(ssid_ts, (tx, rect.y + 10))

            # Khóa bảo mật nếu có
            if row.get("secure"):
                lx = tx + ssid_ts.get_width() + 8
                self._draw_lock(surface, lx, rect.y + 12)

            sub_info = f"{row.get('auth', 'OPEN')}  •  Tín hiệu: {row.get('signal', 0)}%"
            surface.blit(self.theme.font_small.render(sub_info, True, Colors.TEXT_MUTED), (tx, rect.y + 32))

        surface.set_clip(old_clip)

    def _draw_password_panel(self, surface: pygame.Surface):
        panel = pygame.Rect(self.MARGIN, 96, 800 - 2 * self.MARGIN, 112)
        pygame.draw.rect(surface, Colors.GREEN_BG, panel, border_radius=16)
        pygame.draw.rect(surface, Colors.GREEN_BORDER, panel, 1, border_radius=16)

        title = self.theme.font_title.render(f"Nhập mật khẩu cho mạng: {self.pending_ssid}", True, Colors.TEXT_DARK)
        surface.blit(title, (self.MARGIN + 20, panel.y + 18))
        self.pw_input.draw(surface)

    def _draw_signal_bars(self, surface: pygame.Surface, box: pygame.Rect, color, pct: int):
        level = 4 if pct >= 75 else (3 if pct >= 50 else (2 if pct >= 25 else 1))
        bar_w = 4
        gap = 2
        total_w = bar_w * 4 + gap * 3
        start_x = box.centerx - total_w // 2
        base_y = box.bottom - 8
        heights = [0.35, 0.55, 0.75, 1.0]

        for i, h in enumerate(heights):
            hh = int(20 * h)
            r = pygame.Rect(start_x + i * (bar_w + gap), base_y - hh, bar_w, hh)
            c = color if i < level else (210, 215, 212)
            pygame.draw.rect(surface, c, r, border_radius=2)

    def _draw_lock(self, surface: pygame.Surface, x: int, y: int):
        color = Colors.TEXT_MUTED
        pygame.draw.rect(surface, color, (x, y + 5, 10, 8), border_radius=2)
        pygame.draw.arc(surface, color, (x + 1, y, 8, 8), 0, math.pi, 2)

    def _draw_toast(self, surface: pygame.Surface, snap):
        msg, ok, ts = snap["result"]
        if not msg or time.time() - ts > 4:
            return
        col = (60, 160, 100) if ok else Colors.COLOR_DANGER
        ts_surf = self.theme.font_small_bold.render(msg, True, self.COLOR_WHITE)
        rect = pygame.Rect(0, 0, ts_surf.get_width() + 28, 34)
        rect.midbottom = (400, 470)
        pygame.draw.rect(surface, col, rect, border_radius=9)
        surface.blit(ts_surf, ts_surf.get_rect(center=rect.center))
