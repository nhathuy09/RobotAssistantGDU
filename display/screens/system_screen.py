import math
import time
import os
import pygame
from typing import List, Dict
from display.screens.base_screen import BaseScreen
from display.theme import Colors, Theme
from database.repositories import SystemLogRepository

# Thử lấy thông số thực nếu có psutil
try:
    import psutil
except ImportError:
    psutil = None

class SystemScreen(BaseScreen):
    """Màn hình System Status & Diagnostics chuẩn theo thiết kế BD-1 Forest Green."""

    PAGE_BG = Colors.PAGE_BG
    CARD_BG = Colors.CARD_BG_MUTED
    CARD_BORDER = Colors.CARD_BORDER
    TEXT_MAIN = Colors.TEXT_MAIN
    TEXT_MUTED = Colors.TEXT_MUTED
    GREEN_STATUS = Colors.GREEN_STATUS
    TERMINAL_BG = Colors.TERMINAL_BG

    def __init__(self, app_manager):
        super().__init__(app_manager)

        self.back_btn_rect = pygame.Rect(24, 16, 110, 36)
        self.btn_export_rect = pygame.Rect(670, 216, 92, 30)

        # 3 Card trên
        card_w = 236
        card_h = 120
        gap = 20
        self.card_rpi = pygame.Rect(26, 72, card_w, card_h)
        self.card_hub = pygame.Rect(26 + card_w + gap, 72, card_w, card_h)
        self.card_audio = pygame.Rect(26 + (card_w + gap) * 2, 72, card_w, card_h)

        # Card log dưới
        self.log_card_rect = pygame.Rect(26, 206, 748, 224)
        self.terminal_rect = pygame.Rect(26, 252, 748, 178)
        self.log_scroll_y = 0
        self.log_scroll_dragging = False
        self.log_drag_offset = 0

        # Log mẫu hệ thống
        self.logs: List[Dict[str, str]] = [
            {"time": "09:41:32", "level": "INFO", "msg": "Audio pipeline initialized - input device USB PnP Sound Device"},
            {"time": "09:41:29", "level": "OK", "msg": "OhStem Hub handshake complete on /dev/ttyUSB0"},
            {"time": "09:40:18", "level": "WARN", "msg": "Wi-Fi signal briefly dropped below -70 dBm; connection recovered"},
            {"time": "09:39:56", "level": "INFO", "msg": "DHCP lease renewed - 192.168.1.42"},
            {"time": "09:39:11", "level": "OK", "msg": "All core services healthy"},
        ]

    def _get_cpu_info(self) -> Dict[str, str]:
        temp_str = "42°C"
        cpu_usage = "28%"
        ram_str = "1.8 / 4 GB"

        if psutil:
            try:
                cpu_usage = f"{int(psutil.cpu_percent())}%"
                mem = psutil.virtual_memory()
                ram_str = f"{round(mem.used / (1024**3), 1)} / {round(mem.total / (1024**3))} GB"
            except Exception:
                pass


        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(thermal_path):
            try:
                with open(thermal_path, "r") as f:
                    temp_raw = int(f.read().strip())
                    temp_str = f"{round(temp_raw / 1000.0, 1)}°C"
                    
            except Exception:
                pass

        return {"temp": temp_str, "info": f"CPU {cpu_usage} • RAM {ram_str}"}

    def on_enter(self, **kwargs):
        self.log_scroll_y = 0
        self._refresh_logs()

    def _refresh_logs(self):
        db_logs = SystemLogRepository.get_recent_logs(limit=10)
        if db_logs:
            self.logs = [
                {"time": l["time_str"], "level": l["level"], "msg": f"[{l['component']}] {l['message']}"}
                for l in db_logs
            ]
        self.log_scroll_y = min(self.log_scroll_y, self._get_max_log_scroll())

    def _get_max_log_scroll(self) -> int:
        line_gap = 26
        content_height = len(self.logs) * line_gap
        visible_height = self.terminal_rect.height - 28
        return max(0, content_height - visible_height)

    def _get_log_scrollbar(self):
        track_rect = pygame.Rect(
            self.terminal_rect.right - 14,
            self.terminal_rect.y + 10,
            6,
            self.terminal_rect.height - 20,
        )
        max_scroll = self._get_max_log_scroll()
        if max_scroll <= 0:
            return track_rect, None

        visible_height = self.terminal_rect.height - 28
        content_height = visible_height + max_scroll
        thumb_height = max(24, int(track_rect.height * visible_height / content_height))
        travel = track_rect.height - thumb_height
        thumb_y = track_rect.y + int(travel * self.log_scroll_y / max_scroll)
        return track_rect, pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_height)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn_rect.collidepoint(event.pos):
                self.app_manager.switch_screen("face")
                return True

            if self.btn_export_rect.collidepoint(event.pos):
                export_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "system_event_logs.txt")
                if SystemLogRepository.export_logs_to_file(export_file):
                    SystemLogRepository.log("OK", "SYSTEM", f"Đã xuất nhật ký hệ thống ra file {os.path.basename(export_file)}")
                    self._refresh_logs()
                    print(f"[SYSTEM LOG] Xuất file thành công: {export_file}")
                return True

            _, thumb_rect = self._get_log_scrollbar()
            if thumb_rect and thumb_rect.collidepoint(event.pos):
                self.log_scroll_dragging = True
                self.log_drag_offset = event.pos[1] - thumb_rect.y
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.log_scroll_dragging:
                self.log_scroll_dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION and self.log_scroll_dragging:
            track_rect, thumb_rect = self._get_log_scrollbar()
            if thumb_rect:
                travel = track_rect.height - thumb_rect.height
                thumb_y = max(
                    track_rect.y,
                    min(event.pos[1] - self.log_drag_offset, track_rect.bottom - thumb_rect.height),
                )
                if travel > 0:
                    self.log_scroll_y = int(
                        (thumb_y - track_rect.y) / travel * self._get_max_log_scroll()
                    )
            return True

        elif event.type == pygame.MOUSEWHEEL and self.terminal_rect.collidepoint(pygame.mouse.get_pos()):
            self.log_scroll_y = max(
                0,
                min(self._get_max_log_scroll(), self.log_scroll_y - event.y * 26),
            )
            return True

        return False

    def update(self):
        pass

    def _draw_cpu_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng vi mạch CPU."""
        # Thân chip vuông
        pygame.draw.rect(surface, color, (cx - 7, cy - 7, 14, 14), width=1, border_radius=2)
        pygame.draw.rect(surface, color, (cx - 3, cy - 3, 6, 6))
        # Các chân chip 4 cạnh
        for offset in (-4, 0, 4):
            # Top & Bottom
            pygame.draw.line(surface, color, (cx + offset, cy - 10), (cx + offset, cy - 7), 1)
            pygame.draw.line(surface, color, (cx + offset, cy + 7), (cx + offset, cy + 10), 1)
            # Left & Right
            pygame.draw.line(surface, color, (cx - 10, cy + offset), (cx - 7, cy + offset), 1)
            pygame.draw.line(surface, color, (cx + 7, cy + offset), (cx + 10, cy + offset), 1)

    def _draw_hub_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng liên kết Link."""
        # Hai vòng liên kết lồng nhau
        pygame.draw.circle(surface, color, (cx - 4, cy + 3), 5, 2)
        pygame.draw.circle(surface, color, (cx + 4, cy - 3), 5, 2)
        pygame.draw.line(surface, color, (cx - 2, cy + 1), (cx + 2, cy - 1), 2)

    def _draw_audio_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng loa âm thanh."""
        # Thùng loa & phễu
        pygame.draw.rect(surface, color, (cx - 7, cy - 4, 4, 8))
        points = [(cx - 3, cy - 4), (cx + 2, cy - 8), (cx + 2, cy + 8), (cx - 3, cy + 4)]
        pygame.draw.polygon(surface, color, points)
        # Sóng âm
        pygame.draw.arc(surface, color, (cx, cy - 6, 8, 12), -1.1, 1.1, 2)
        pygame.draw.arc(surface, color, (cx + 3, cy - 9, 10, 18), -1.1, 1.1, 2)

    def draw(self, surface: pygame.Surface):
        surface.fill(self.PAGE_BG)
        mouse_pos = pygame.mouse.get_pos()

        # 1. Header: Back button + Title
        hover_back = self.back_btn_rect.collidepoint(mouse_pos)
        back_col = self.TEXT_MAIN if not hover_back else (80, 85, 95)
        pygame.draw.line(surface, back_col, (self.back_btn_rect.x + 8, self.back_btn_rect.centery), (self.back_btn_rect.x + 14, self.back_btn_rect.centery - 6), 2)
        pygame.draw.line(surface, back_col, (self.back_btn_rect.x + 8, self.back_btn_rect.centery), (self.back_btn_rect.x + 14, self.back_btn_rect.centery + 6), 2)
        back_text = self.theme.get_font(15, bold=True).render("Quay lại", True, back_col)
        surface.blit(back_text, (self.back_btn_rect.x + 20, self.back_btn_rect.centery - back_text.get_height() // 2))

        # Tiêu đề trung tâm
        title_surf = self.theme.get_font(21, bold=True).render("System Status & Diagnostics", True, self.TEXT_MAIN)
        surface.blit(title_surf, (400 - title_surf.get_width() // 2, 22))

        # Đường viền phân cách
        pygame.draw.line(surface, self.CARD_BORDER, (0, 60), (800, 60), 1)

        # 2. Hàng trên: 3 Cards trạng thái
        cpu_data = self._get_cpu_info()
        self._draw_status_card(
            surface,
            self.card_rpi,
            icon_type="cpu",
            title="RASPBERRY PI",
            val=cpu_data["temp"],
            sub=cpu_data["info"],
            status="Healthy",
        )
        self._draw_status_card(
            surface,
            self.card_hub,
            icon_type="hub",
            title="OHSTEM HUB",
            val="Online",
            sub="Serial /dev/ttyUSB0 • 115200",
            status="Connected",
        )
        self._draw_status_card(
            surface,
            self.card_audio,
            icon_type="audio",
            title="AUDIO STREAM",
            val="Active",
            sub="48 kHz • 24 ms latency",
            status="Stable",
        )

        # 3. Khung dưới: System event log
        # Nền card chứa header log
        pygame.draw.rect(surface, self.CARD_BG, self.log_card_rect, border_radius=16)
        pygame.draw.rect(surface, self.CARD_BORDER, self.log_card_rect, width=1, border_radius=16)

        # Header của log card
        log_title = self.theme.get_font(15, bold=True).render("System event log", True, self.TEXT_MAIN)
        surface.blit(log_title, (self.log_card_rect.x + 16, self.log_card_rect.y + 14))

        # Badge "Live"
        badge_rect = pygame.Rect(self.log_card_rect.x + 16 + log_title.get_width() + 10, self.log_card_rect.y + 14, 38, 20)
        pygame.draw.rect(surface, self.GREEN_STATUS, badge_rect, border_radius=10)
        live_ts = self.theme.get_font(10, bold=True).render("Live", True, (255, 255, 255))
        surface.blit(live_ts, live_ts.get_rect(center=badge_rect.center))

        # Nút "Export log"
        h_exp = self.btn_export_rect.collidepoint(mouse_pos)
        bg_exp = (248, 246, 240) if h_exp else (255, 255, 255)
        pygame.draw.rect(surface, bg_exp, self.btn_export_rect, border_radius=10)
        pygame.draw.rect(surface, (215, 210, 202), self.btn_export_rect, width=1, border_radius=10)
        exp_surf = self.theme.get_font(12, bold=True).render("Export log", True, self.TEXT_MAIN)
        surface.blit(exp_surf, exp_surf.get_rect(center=self.btn_export_rect.center))

        # Terminal Console màu đen xám than
        pygame.draw.rect(surface, self.TERMINAL_BG, self.terminal_rect, border_bottom_left_radius=16, border_bottom_right_radius=16)

        # Render danh sách logs
        log_font = self.theme.get_font(12)
        line_gap = 26
        ly = self.terminal_rect.y + 14 - self.log_scroll_y
        old_clip = surface.get_clip()
        surface.set_clip(self.terminal_rect)

        for item in self.logs:
            # 1. Thời gian
            t_surf = log_font.render(item["time"], True, (170, 175, 180))
            surface.blit(t_surf, (self.terminal_rect.x + 16, ly))

            # 2. Tag Level
            lvl = item["level"]
            if lvl == "OK":
                l_col = (100, 190, 115)
            elif lvl == "WARN":
                l_col = (235, 170, 65)
            else:
                l_col = (240, 245, 250)
            l_surf = log_font.render(lvl, True, l_col)
            surface.blit(l_surf, (self.terminal_rect.x + 92, ly))

            # 3. Message
            m_surf = log_font.render(item["msg"], True, (220, 225, 230))
            surface.blit(m_surf, (self.terminal_rect.x + 148, ly))

            ly += line_gap

        surface.set_clip(old_clip)

        # Thanh cuộn dọc cho danh sách log
        track_rect, thumb_rect = self._get_log_scrollbar()
        if thumb_rect:
            pygame.draw.rect(surface, (28, 57, 47), track_rect, border_radius=3)
            pygame.draw.rect(surface, (113, 157, 139), thumb_rect, border_radius=3)

        # 4. Footer dưới cùng màn hình
        # Bên trái: Chấm xanh Live telemetry active
        pygame.draw.circle(surface, self.GREEN_STATUS, (32, 452), 4)
        tele_surf = self.theme.get_font(12).render("Live telemetry active", True, self.TEXT_MUTED)
        surface.blit(tele_surf, (42, 452 - tele_surf.get_height() // 2))

        # Bên phải: Last updated just now
        upd_surf = self.theme.get_font(12).render("Last updated just now", True, self.TEXT_MUTED)
        surface.blit(upd_surf, (774 - upd_surf.get_width(), 452 - upd_surf.get_height() // 2))

    def _draw_status_card(self, surface: pygame.Surface, rect: pygame.Rect, icon_type: str, title: str, val: str, sub: str, status: str):
        """Vẽ 1 trong 3 card trạng thái ở hàng trên."""
        pygame.draw.rect(surface, self.CARD_BG, rect, border_radius=16)
        pygame.draw.rect(surface, self.CARD_BORDER, rect, width=1, border_radius=16)

        # Icon box trắng bên trái
        icon_box = pygame.Rect(rect.x + 16, rect.y + 16, 40, 40)
        pygame.draw.rect(surface, (255, 255, 255), icon_box, border_radius=10)
        pygame.draw.rect(surface, (226, 222, 214), icon_box, width=1, border_radius=10)

        if icon_type == "cpu":
            self._draw_cpu_icon(surface, icon_box.centerx, icon_box.centery, self.TEXT_MAIN)
        elif icon_type == "hub":
            self._draw_hub_icon(surface, icon_box.centerx, icon_box.centery, self.TEXT_MAIN)
        else:
            self._draw_audio_icon(surface, icon_box.centerx, icon_box.centery, self.TEXT_MAIN)

        # Tiêu đề nhỏ (in hoa)
        t_surf = self.theme.get_font(10, bold=True).render(title, True, (110, 115, 125))
        surface.blit(t_surf, (rect.x + 66, rect.y + 14))

        # Giá trị to đậm
        v_surf = self.theme.get_font(21, bold=True).render(val, True, self.TEXT_MAIN)
        surface.blit(v_surf, (rect.x + 66, rect.y + 28))

        # Dòng thông số
        s_surf = self.theme.get_font(11).render(sub, True, (80, 85, 95))
        surface.blit(s_surf, (rect.x + 66, rect.y + 57))

        # Chấm xanh & Trạng thái dưới
        dot_y = rect.y + 92
        pygame.draw.circle(surface, self.GREEN_STATUS, (rect.x + 70, dot_y), 4)
        stat_surf = self.theme.get_font(12).render(status, True, (80, 85, 95))
        surface.blit(stat_surf, (rect.x + 80, dot_y - stat_surf.get_height() // 2))
