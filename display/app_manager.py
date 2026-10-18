import json
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

import pygame

from display.theme import Theme, Colors
from display.components.asissitive_touch import AssistiveTouch
from display.screens.base_screen import BaseScreen
from display.screens.face_screen import FaceScreen
from display.screens.connectivity_screen import ConnectivityScreen
from display.screens.persona_screen import PersonaScreen
from display.screens.system_screen import SystemScreen
from display.screens.auth_screen import AuthScreen

try:
    from feature.wifi import WifiManager
except ImportError:
    WifiManager = None


class AppManager:
    """
    Trình quản lý trung tâm (Application Manager) điều phối:
    - Quản lý vòng đời màn hình (Screen Lifecycle)
    - Hệ thống nút ảo AssistiveTouch
    - Quản lý cấu hình robot (robot_settings.json)
    - Luồng lắng nghe UDP biểu cảm (cổng 5005)
    - Vòng lặp sự kiện chính (Main Event Loop)
    """

    SETTINGS_PATH = Path(__file__).resolve().parent.parent / "robot_settings.json"
    UDP_IP = "0.0.0.0"
    UDP_PORT = 5005

    def __init__(self, width: int = 800, height: int = 480):
        self.width = width
        self.height = height

        self._enable_dpi_awareness()
        pygame.init()

        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("BD-1 Dashboard • Modular Architecture")
        self.clock = pygame.time.Clock()

        self.theme = Theme()
        self.settings = self._load_settings()

        # Quản lý Wi-Fi
        self.wifi = WifiManager() if WifiManager else None

        # Quản lý màn hình
        self.screens: Dict[str, BaseScreen] = {}
        self.current_screen_name = "face"
        self.current_screen: Optional[BaseScreen] = None

        self._init_screens()

        # Nút ảo nổi
        self.assistive_touch = AssistiveTouch(
            screen_size=(self.width, self.height),
            on_navigate=self.switch_screen,
        )

        # UDP listener cho biểu cảm khuôn mặt
        self.stop_event = threading.Event()
        self.udp_thread = self._start_udp_thread()

        self.running = False

    @staticmethod
    def _enable_dpi_awareness():
        if sys.platform == "win32":
            import ctypes

            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

    def _load_settings(self) -> dict:
        if not self.SETTINGS_PATH.exists():
            return {}

        try:
            with self.SETTINGS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as err:
            print(f"[SETTINGS] Không thể nạp {self.SETTINGS_PATH}: {err}")
            return {}

    def persist_settings(self) -> Optional[str]:
        """Lưu settings an toàn qua file tạm; trả None nếu thành công, chuỗi lỗi nếu thất bại."""
        tmp_path = self.SETTINGS_PATH.with_name(self.SETTINGS_PATH.name + ".tmp")

        try:
            self.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp_path, self.SETTINGS_PATH)
            return None
        except (OSError, TypeError, ValueError) as err:
            print(f"[SETTINGS] Lưu thất bại: {err}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return f"Lỗi lưu cấu hình: {err}"

    def _init_screens(self):
        self.screens = {
            "face": FaceScreen(self, show_gallery=False),
            "faces_gallery": FaceScreen(self, show_gallery=True),
            "wifi": ConnectivityScreen(self),
            "persona": PersonaScreen(self),
            "system": SystemScreen(self),
            "auth": AuthScreen(self),
        }
        self.current_screen = self.screens[self.current_screen_name]
        self.current_screen.on_enter()

    def register_screen(self, name: str, screen: BaseScreen):
        """Đăng ký hoặc thay thế một màn hình."""
        self.screens[name] = screen

    def switch_screen(self, name: str, **kwargs):
        """Chuyển màn hình, gọi đúng hook rời màn hình và vào màn hình mới."""
        if name not in self.screens:
            print(f"[NAV] Không tìm thấy màn hình: {name}")
            return

        if self.current_screen is self.screens[name]:
            # Cho phép gọi lại on_enter để đổi chế độ, ví dụ gallery=True,
            # nhưng không gọi on_leave trên chính màn hình đang hiển thị.
            self.current_screen.on_enter(**kwargs)
            self.current_screen_name = name
            return

        if self.current_screen:
            self.current_screen.on_leave()

        self.current_screen_name = name
        self.current_screen = self.screens[name]
        self.assistive_touch.current_screen_id = name if hasattr(self, "assistive_touch") else name
        self.current_screen.on_enter(**kwargs)

    def _start_udp_thread(self) -> threading.Thread:
        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            try:
                sock.bind((self.UDP_IP, self.UDP_PORT))
                sock.settimeout(0.5)
                print(f"[UDP] Đang lắng nghe dữ liệu biểu cảm tại cổng {self.UDP_PORT}")
            except OSError as err:
                print(f"[UDP] Cổng {self.UDP_PORT} bận hoặc không thể mở: {err}")
                sock.close()
                return

            try:
                while not self.stop_event.is_set():
                    try:
                        data, _ = sock.recvfrom(1024)
                        state = data.decode("utf-8", errors="ignore").strip().upper()
                        # Không cập nhật pygame/UI từ thread UDP; chuyển trạng thái
                        # vào hàng đợi để xử lý ở main thread.
                        if state:
                            self._udp_states.append(state)
                    except socket.timeout:
                        continue
                    except OSError:
                        if not self.stop_event.is_set():
                            print("[UDP] Socket đã đóng ngoài dự kiến.")
                        break
                    except Exception as err:
                        print(f"[UDP ERROR] {err}")
            finally:
                sock.close()

        self._udp_states = []
        self._udp_states_lock = threading.Lock()
        th = threading.Thread(target=listen, daemon=True, name="bd1-udp-listener")
        th.start()
        return th

    def _process_udp_states(self):
        """Áp dụng biểu cảm trong main thread để tránh truy cập pygame từ thread nền."""
        with self._udp_states_lock:
            states = self._udp_states[:]
            self._udp_states.clear()

        if not states:
            return

        state = states[-1]  # Chỉ cần trạng thái mới nhất.
        face_scr = self.screens.get("face")
        if isinstance(face_scr, FaceScreen):
            face = getattr(face_scr, "face", None)
            if face is not None and hasattr(face, "set_state"):
                face.set_state(state)

    def run(self):
        self.running = True

        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        if self.current_screen_name != "face":
                            self.switch_screen("face")
                        else:
                            self.running = False
                        break

                    if self.assistive_touch.handle_event(event):
                        continue

                    if self.current_screen:
                        self.current_screen.handle_event(event)

                if not self.running:
                    break

                self._process_udp_states()

                if self.current_screen:
                    self.current_screen.update()
                self.assistive_touch.update()

                if self.current_screen:
                    self.current_screen.draw(self.screen)

                kb_active = (
                    self.current_screen_name == "wifi"
                    and isinstance(self.current_screen, ConnectivityScreen)
                    and getattr(getattr(self.current_screen, "keyboard", None), "visible", False)
                )
                if not kb_active:
                    self.assistive_touch.draw(self.screen)

                pygame.display.flip()
                self.clock.tick(self.theme.FPS)

        except KeyboardInterrupt:
            print("\n[APP] Nhận tín hiệu thoát chương trình.")
        finally:
            self.stop()

    def stop(self):
        """Dừng vòng lặp và các tài nguyên nền trước khi đóng pygame."""
        self.running = False
        self.stop_event.set()

        if self.wifi and hasattr(self.wifi, "stop"):
            try:
                self.wifi.stop()
            except Exception as err:
                print(f"[WIFI] Lỗi khi dừng WifiManager: {err}")

        udp_thread = getattr(self, "udp_thread", None)
        if udp_thread and udp_thread.is_alive():
            udp_thread.join(timeout=1.0)

        pygame.quit()
