import math
import time
import pygame
from display.screens.base_screen import BaseScreen
from display.theme import Colors
from display.components.virtual_keyboard import VirtualKeyboard
from display.components.input_field import InputField
from feature.bluetooth import BluetoothManager

class ConnectivityScreen(BaseScreen):
    """Màn hình cấu hình Wi-Fi & Bluetooth Audio theo phong cách hiện đại với bảng màu BD-1."""

    PAGE_BG = Colors.PAGE_BG
    CARD_BG = Colors.CARD_BG_MUTED
    CARD_BORDER = Colors.CARD_BORDER
    TEXT_MAIN = Colors.TEXT_MAIN
    TEXT_MUTED = Colors.TEXT_MUTED
    CONNECTED_BG = Colors.CONNECTED_BG
    TAB_BG = Colors.TAB_BG
    SAGE_MUTED = Colors.SAGE_MUTED

    ROW_H = 68
    ROW_GAP = 10

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.wifi = app_manager.wifi
        self.bluetooth = BluetoothManager()

        self.current_tab = "wifi"  # "wifi" hoặc "bluetooth"

        # Tọa độ Layout
        self.back_btn_rect = pygame.Rect(24, 16, 110, 36)
        self.tab_container_rect = pygame.Rect(24, 72, 752, 48)
        self.tab_wifi_rect = pygame.Rect(28, 76, 370, 40)
        self.tab_bt_rect = pygame.Rect(402, 76, 370, 40)

        self.list_top = 156
        self.list_rect = pygame.Rect(24, self.list_top, 752, 480 - 15 - self.list_top)

        self.scroll_y = 0
        self.is_dragging_list = False
        self.drag_start_y = 0
        self.drag_start_scroll = 0
        self.pending_row = None

        self.last_networks = []
        self.row_rects = []

        # Bàn phím ảo nhập mật khẩu Wi-Fi
        self.keyboard = VirtualKeyboard(
            top_y=220,
            on_submit=self._on_submit_password,
            on_cancel=self._on_cancel_password,
        )
        self.pw_input = InputField(
            rect=pygame.Rect(114, 150, 572, 48),
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
        if self.wifi:
            try:
                self.wifi.scan(force=True)
            except Exception as exc:
                print(f"[Wi-Fi] Scan lỗi: {exc}")
        if self.bluetooth:
            self.bluetooth.scan()

    def _on_submit_password(self, *_args):
        if not self.pending_ssid or not self.wifi:
            self.keyboard.close()
            return
        try:
            self.wifi.connect(self.pending_ssid, self.pw_input.value)
        except Exception as exc:
            print(f"[Wi-Fi] Lỗi kết nối {self.pending_ssid}: {exc}")
        finally:
            self.keyboard.close()

    def _on_cancel_password(self, *_args):
        self.keyboard.close()
        self.pending_ssid = ""

    def handle_event(self, event: pygame.event.Event) -> bool:
        # Khi bàn phím ảo mở
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
            # Nút Quay lại
            if self.back_btn_rect.collidepoint(event.pos):
                self.app_manager.switch_screen("face")
                return True

            # Tab chuyển đổi
            if self.tab_wifi_rect.collidepoint(event.pos):
                if self.current_tab != "wifi":
                    self.current_tab = "wifi"
                    self.scroll_y = 0
                    if self.wifi:
                        self.wifi.scan(force=True)
                return True

            if self.tab_bt_rect.collidepoint(event.pos):
                if self.current_tab != "bluetooth":
                    self.current_tab = "bluetooth"
                    self.scroll_y = 0
                    if self.bluetooth:
                        self.bluetooth.scan()
                return True

            # Nút Scan / Refresh
            scan_rect = pygame.Rect(700, 126, 76, 28)
            if scan_rect.collidepoint(event.pos):
                if self.current_tab == "wifi" and self.wifi:
                    self.wifi.scan(force=True)
                elif self.current_tab == "bluetooth" and self.bluetooth:
                    self.bluetooth.scan()
                return True

            # Click vào danh sách
            if self.list_rect.collidepoint(event.pos):
                for rect, item in self.row_rects:
                    if rect.colliderect(self.list_rect) and rect.collidepoint(event.pos):
                        self.pending_row = item
                        self.drag_start_y = event.pos[1]
                        self.drag_start_scroll = self.scroll_y
                        self.is_dragging_list = False
                        return True

                self.drag_start_y = event.pos[1]
                self.drag_start_scroll = self.scroll_y
                self.is_dragging_list = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[0] and (self.pending_row is not None or self.list_rect.collidepoint(event.pos)):
                dy = event.pos[1] - self.drag_start_y
                if abs(dy) > 6:
                    self.is_dragging_list = True
                    self.pending_row = None
                    total_h = len(self.row_rects) * (self.ROW_H + self.ROW_GAP)
                    max_scroll = max(0, total_h - self.list_rect.height)
                    self.scroll_y = max(0, min(self.drag_start_scroll - dy, max_scroll))
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pending_row is not None and not self.is_dragging_list:
                item = self.pending_row
                self.pending_row = None
                self._activate_item(item, event.pos)
                return True
            was_dragging = self.is_dragging_list
            self.pending_row = None
            self.is_dragging_list = False
            return was_dragging

        elif event.type == pygame.MOUSEWHEEL:
            if self.list_rect.collidepoint(pygame.mouse.get_pos()):
                total_h = len(self.row_rects) * (self.ROW_H + self.ROW_GAP)
                max_scroll = max(0, total_h - self.list_rect.height)
                self.scroll_y = max(0, min(self.scroll_y - event.y * 46, max_scroll))
                return True

        return False

    def _activate_item(self, item: dict, click_pos):
        if self.current_tab == "wifi":
            ssid = item.get("ssid", "")
            if not ssid:
                return

            # Nếu nhấn nút Forget khi đang kết nối
            if item.get("in_use"):
                if self.wifi:
                    self.wifi.forget(ssid)
                return

            # Kết nối mạng
            if item.get("saved") and item.get("secure"):
                self.wifi.connect(ssid, None)
            elif not item.get("secure"):
                self.wifi.connect(ssid, "")
            else:
                self.pending_ssid = ssid
                self.pw_input.value = ""
                self.pw_input.show_password = False
                self.pw_input.placeholder = f"Nhập mật khẩu cho {ssid}..."
                self.pw_input.set_focus(True)
                self.keyboard.open(self.pw_input)
        else:
            # Bluetooth item
            dev_id = item.get("id")
            snap = self.bluetooth.snapshot() if self.bluetooth else {}
            if snap.get("connecting_id"):
                return  # Đang có thiết bị trong tiến trình kết nối

            if item.get("connected"):
                self.bluetooth.disconnect(dev_id)
            else:
                self.bluetooth.connect(dev_id)

    def update(self):
        self.keyboard.update()
        self.pw_input.update()

    def _draw_wifi_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng Wi-Fi vector."""
        pygame.draw.circle(surface, color, (cx, cy + 5), 2)
        pygame.draw.arc(surface, color, (cx - 7, cy - 2, 14, 12), 0.75, 2.39, 2)
        pygame.draw.arc(surface, color, (cx - 12, cy - 7, 24, 18), 0.75, 2.39, 2)

    def _draw_bt_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng Bluetooth vector."""
        # Trục thẳng
        pygame.draw.line(surface, color, (cx, cy - 9), (cx, cy + 9), 2)
        # Nét chéo & tam giác
        points = [(cx - 5, cy - 5), (cx + 5, cy + 4), (cx, cy + 9), (cx, cy - 9), (cx + 5, cy - 4), (cx - 5, cy + 5)]
        pygame.draw.lines(surface, color, False, points, 2)

    def draw(self, surface: pygame.Surface):
        surface.fill(self.PAGE_BG)
        mouse_pos = pygame.mouse.get_pos()

        # 1. Header: Back button + Title
        hover_back = self.back_btn_rect.collidepoint(mouse_pos)
        back_col = self.TEXT_MAIN if not hover_back else (80, 85, 95)
        # Chevron <
        pygame.draw.line(surface, back_col, (self.back_btn_rect.x + 8, self.back_btn_rect.centery), (self.back_btn_rect.x + 14, self.back_btn_rect.centery - 6), 2)
        pygame.draw.line(surface, back_col, (self.back_btn_rect.x + 8, self.back_btn_rect.centery), (self.back_btn_rect.x + 14, self.back_btn_rect.centery + 6), 2)
        back_text = self.theme.get_font(15, bold=True).render("Quay lại", True, back_col)
        surface.blit(back_text, (self.back_btn_rect.x + 20, self.back_btn_rect.centery - back_text.get_height() // 2))

        # Tiêu đề trung tâm
        title_surf = self.theme.get_font(21, bold=True).render("Connectivity Settings", True, self.TEXT_MAIN)
        surface.blit(title_surf, (400 - title_surf.get_width() // 2, 22))

        # Đường viền phân cách
        pygame.draw.line(surface, self.CARD_BORDER, (0, 60), (800, 60), 1)

        # 2. Tab Bar: Wi-Fi Networks / Bluetooth Audio
        pygame.draw.rect(surface, self.TAB_BG, self.tab_container_rect, border_radius=14)

        # Tab Wi-Fi
        is_wifi_active = (self.current_tab == "wifi")
        if is_wifi_active:
            pygame.draw.rect(surface, (255, 255, 255), self.tab_wifi_rect, border_radius=11)
            pygame.draw.rect(surface, self.CARD_BORDER, self.tab_wifi_rect, width=1, border_radius=11)
            t_col = self.TEXT_MAIN
        else:
            t_col = self.TEXT_MUTED
        self._draw_wifi_icon(surface, self.tab_wifi_rect.x + 115, self.tab_wifi_rect.centery, t_col)
        w_lbl = self.theme.get_font(14, bold=is_wifi_active).render("Wi-Fi Networks", True, t_col)
        surface.blit(w_lbl, (self.tab_wifi_rect.x + 130, self.tab_wifi_rect.centery - w_lbl.get_height() // 2))

        # Tab Bluetooth
        is_bt_active = (self.current_tab == "bluetooth")
        if is_bt_active:
            pygame.draw.rect(surface, (255, 255, 255), self.tab_bt_rect, border_radius=11)
            pygame.draw.rect(surface, self.CARD_BORDER, self.tab_bt_rect, width=1, border_radius=11)
            b_col = self.TEXT_MAIN
        else:
            b_col = self.TEXT_MUTED
        self._draw_bt_icon(surface, self.tab_bt_rect.x + 115, self.tab_bt_rect.centery, b_col)
        b_lbl = self.theme.get_font(14, bold=is_bt_active).render("Bluetooth Audio", True, b_col)
        surface.blit(b_lbl, (self.tab_bt_rect.x + 130, self.tab_bt_rect.centery - b_lbl.get_height() // 2))

        # Nếu bàn phím ảo đang mở (khi nhập mật khẩu Wi-Fi)
        if self.keyboard.visible:
            self._draw_password_panel(surface)
            self.keyboard.draw(surface)
            return

        # 3. Section Header
        if is_wifi_active:
            sec_title = "AVAILABLE NETWORKS"
            is_scanning = bool(self.wifi and self.wifi.snapshot().get("scanning"))
        else:
            sec_title = "AVAILABLE DEVICES"
            is_scanning = bool(self.bluetooth and self.bluetooth.snapshot().get("scanning", False))

        sec_surf = self.theme.get_font(11, bold=True).render(sec_title, True, (80, 85, 95))
        surface.blit(sec_surf, (26, 134))

        # Nút Scan / Refresh
        scan_rect = pygame.Rect(700, 126, 76, 28)
        if is_scanning:
            scan_surf = self.theme.get_font(12).render("Scanning...", True, (140, 145, 155))
            surface.blit(scan_surf, (776 - scan_surf.get_width(), 132))
        else:
            h_scan = scan_rect.collidepoint(mouse_pos)
            pygame.draw.rect(surface, (246, 244, 238) if h_scan else (255, 255, 255), scan_rect, border_radius=10)
            pygame.draw.rect(surface, (215, 210, 202), scan_rect, width=1, border_radius=10)
            scan_txt = self.theme.get_font(12, bold=True).render("Quét lại", True, self.TEXT_MAIN)
            surface.blit(scan_txt, scan_txt.get_rect(center=scan_rect.center))

        # 4. Danh sách Items
        self._draw_list_content(surface, mouse_pos)

    def _draw_list_content(self, surface: pygame.Surface, mouse_pos):
        self.row_rects = []
        old_clip = surface.get_clip()
        surface.set_clip(self.list_rect)

        connecting_id = None
        if self.current_tab == "wifi":
            snap = self.wifi.snapshot() if self.wifi else {}
            networks = snap.get("networks", [])
            if not networks:
                networks = [
                    {"ssid": "OhStem Lab", "signal": 95, "secure": True, "in_use": True, "freq": "5 GHz • Excellent"},
                    {"ssid": "MakerSpace Guest", "signal": 75, "secure": True, "in_use": False, "freq": "2.4 GHz • Good"},
                    {"ssid": "University_IoT", "signal": 85, "secure": True, "in_use": False, "freq": "5 GHz • Secured"},
                ]
            items = networks
        else:
            bt_snap = self.bluetooth.snapshot() if self.bluetooth else {}
            items = bt_snap.get("devices", [])
            connecting_id = bt_snap.get("connecting_id")

        y = self.list_top - self.scroll_y
        for item in items:
            rect = pygame.Rect(self.list_rect.x, y, self.list_rect.width, self.ROW_H)
            self.row_rects.append((rect, item))

            if rect.bottom >= self.list_rect.top and rect.top <= self.list_rect.bottom:
                # Nền card item
                pygame.draw.rect(surface, self.CARD_BG, rect, border_radius=16)
                pygame.draw.rect(surface, self.CARD_BORDER, rect, width=1, border_radius=16)

                # Icon trong hình tròn trắng bên trái
                icon_circle = pygame.Rect(rect.x + 12, rect.centery - 20, 40, 40)
                pygame.draw.rect(surface, (255, 255, 255), icon_circle, border_radius=20)
                pygame.draw.rect(surface, (226, 222, 214), icon_circle, width=1, border_radius=20)

                if self.current_tab == "wifi":
                    self._draw_wifi_icon(surface, icon_circle.centerx, icon_circle.centery, self.TEXT_MAIN)
                    name = item.get("ssid", "Unknown")
                    sub_info = item.get("freq") or ("5 GHz • Excellent" if item.get("signal", 0) > 80 else "2.4 GHz • Good")
                    is_connected = item.get("in_use", False)
                    is_connecting = False
                else:
                    self._draw_bt_icon(surface, icon_circle.centerx, icon_circle.centery, self.TEXT_MAIN)
                    name = item.get("name", "Bluetooth Device")
                    status_str = item.get("status", "Ready")
                    sub_info = f"{item.get('type', 'Audio')} • {status_str}"
                    is_connected = item.get("connected", False)
                    dev_id = item.get("id")
                    is_connecting = (dev_id == connecting_id or status_str == "Connecting...")

                # Tên item & Sub info
                name_surf = self.theme.get_font(15, bold=True).render(name, True, self.TEXT_MAIN)
                surface.blit(name_surf, (rect.x + 64, rect.y + 14))

                sub_surf = self.theme.get_font(12).render(sub_info, True, self.TEXT_MUTED)
                surface.blit(sub_surf, (rect.x + 64, rect.y + 37))

                # Nút hành động bên phải
                if is_connecting:
                    # Trạng thái đang kết nối
                    btn_rect = pygame.Rect(rect.right - 108, rect.centery - 18, 96, 36)
                    pygame.draw.rect(surface, (238, 235, 226), btn_rect, border_radius=12)
                    pygame.draw.rect(surface, (215, 210, 202), btn_rect, width=1, border_radius=12)
                    conn_lbl = self.theme.get_font(12, bold=True).render("Connecting...", True, (110, 115, 125))
                    surface.blit(conn_lbl, conn_lbl.get_rect(center=btn_rect.center))
                elif is_connected:
                    # Badge "Connected" màu xanh rêu
                    badge_rect = pygame.Rect(rect.right - 156, rect.centery - 16, 76, 32)
                    pygame.draw.rect(surface, self.CONNECTED_BG, badge_rect, border_radius=16)
                    conn_text = self.theme.get_font(11, bold=True).render("Connected", True, (255, 255, 255))
                    surface.blit(conn_text, conn_text.get_rect(center=badge_rect.center))

                    # Chữ Forget / Disconnect
                    forget_label = "Forget" if self.current_tab == "wifi" else "Disconnect"
                    forget_surf = self.theme.get_font(14, bold=True).render(forget_label, True, self.TEXT_MAIN)
                    surface.blit(forget_surf, (rect.right - 64, rect.centery - forget_surf.get_height() // 2))
                else:
                    # Nút "Connect"
                    btn_rect = pygame.Rect(rect.right - 96, rect.centery - 18, 82, 36)
                    h_btn = btn_rect.collidepoint(mouse_pos)
                    bg_btn = (246, 244, 238) if h_btn else (255, 255, 255)
                    pygame.draw.rect(surface, bg_btn, btn_rect, border_radius=12)
                    pygame.draw.rect(surface, (215, 210, 202), btn_rect, width=1, border_radius=12)

                    conn_lbl = self.theme.get_font(13, bold=True).render("Connect", True, self.TEXT_MAIN)
                    surface.blit(conn_lbl, conn_lbl.get_rect(center=btn_rect.center))

            y += self.ROW_H + self.ROW_GAP

        surface.set_clip(old_clip)

    def _draw_password_panel(self, surface: pygame.Surface):
        """Khung nhập mật khẩu Wi-Fi khi mở bàn phím ảo."""
        panel_rect = pygame.Rect(80, 80, 640, 130)
        pygame.draw.rect(surface, (255, 255, 255), panel_rect, border_radius=16)
        pygame.draw.rect(surface, (226, 222, 214), panel_rect, width=1, border_radius=16)

        title = self.theme.get_font(15, bold=True).render(f"Mật khẩu cho {self.pending_ssid}", True, self.TEXT_MAIN)
        surface.blit(title, (panel_rect.centerx - title.get_width() // 2, panel_rect.y + 16))

        self.pw_input.rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 52, panel_rect.width - 60, 48)
        self.pw_input.draw(surface)
