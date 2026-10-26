import os
import socket
import sys
import threading
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
from display.screens.pin_screen import PinScreen
from database.repositories import AdminRepository, SystemLogRepository, SettingsRepository

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

try:
    from feature.wifi import WifiManager
except ImportError:
    WifiManager = None


class AppManager:

    def __init__(self, width: int = 800, height: int = 480):
        self.width = width
        self.height = height

        self._enable_dpi_awareness()
        # pygame.init()
        pygame.display.init()
        pygame.font.init() 
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("BD-1 Dashboard • Modular Architecture")
        self.clock = pygame.time.Clock()

        self.theme = Theme()
        # settings dict không còn dùng để lưu trữ; các module đọc thẳng từ DB repository
        self.settings: Dict = {}

        # Quản lý Wi-Fi
        self.wifi = WifiManager() if WifiManager else None

        # Trạng thái xác thực
        self.is_authenticated: bool = False

        # Quản lý màn hình
        self.screens: Dict[str, BaseScreen] = {}
        self.current_screen_name = "face"   # sẽ được ghi đè trong _init_screens
        self.current_screen: Optional[BaseScreen] = None

        self._init_screens()

        # Nút ảo nổi
        self.assistive_touch = AssistiveTouch(
            screen_size=(self.width, self.height),
            on_navigate=self._navigate_with_auth,
            get_auth=lambda: self.is_authenticated,
        )
        self._pending_state: Optional[str] = None
        self._state_lock = threading.Lock()
        self._udp_stop = threading.Event()
        self._start_udp_listener()

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

    def persist_settings(self) -> Optional[str]:
        """Phương thức tương thích ngược – không thực hiện gì vì settings nay lưu trong SQLite."""
        return None

    def _init_screens(self):
        self.screens = {
            "face": FaceScreen(self, show_gallery=False),
            "faces_gallery": FaceScreen(self, show_gallery=True),
            "wifi": ConnectivityScreen(self),
            "persona": PersonaScreen(self),
            "system": SystemScreen(self),
            "auth": AuthScreen(self),
            "pin": PinScreen(self),
        }

        # Xác định màn hình khởi động dựa trên trạng thái tài khoản trong Database
        if not AdminRepository.is_registered():
            # Chưa có tài khoản → bắt buộc đăng ký
            self.current_screen_name = "auth"
            start_kwargs = {"mode": "register"}
        else:
            # Đã có tài khoản → yêu cầu đăng nhập
            self.current_screen_name = "auth"
            start_kwargs = {"mode": "login"}

        self.current_screen = self.screens[self.current_screen_name]
        self.current_screen.on_enter(**start_kwargs)

    def register_screen(self, name: str, screen: BaseScreen):
        """Đăng ký hoặc thay thế một màn hình."""
        self.screens[name] = screen

    def switch_screen(self, name: str, **kwargs):
        """Chuyển màn hình, yêu cầu xác thực mã PIN cho các trang cấu hình."""
        PROTECTED = {"persona", "system", "wifi", "faces_gallery"}
        pin_verified = kwargs.pop("pin_verified", False)

        if name in PROTECTED and not pin_verified:
            # Nếu chưa đăng nhập tài khoản admin ban đầu
            if not self.is_authenticated:
                self.switch_screen("auth", mode="login")
                return
            # Đã đăng nhập nhưng cần nhập mã PIN để vào trang cấu hình
            self.switch_screen("pin", target_screen=name, **kwargs)
            return

        if name not in self.screens:
            print(f"[NAV] Không tìm thấy màn hình: {name}")
            return

        if self.current_screen is self.screens[name]:
            self.current_screen.on_enter(**kwargs)
            self.current_screen_name = name
            return

        if self.current_screen:
            self.current_screen.on_leave()

        self.current_screen_name = name
        self.current_screen = self.screens[name]
        self.assistive_touch.current_screen_id = name
        self.current_screen.on_enter(**kwargs)

    def _navigate_with_auth(self, name: str) -> None:
        """Điều hướng từ AssistiveTouch."""
        self.switch_screen(name)

    def login(self) -> None:
        """Đánh dấu đã xác thực và chuyển đến màn hình chính."""
        self.is_authenticated = True
        SystemLogRepository.log("INFO", "AUTH", "Người dùng đã đăng nhập vào hệ thống UI.")
        self.switch_screen("face")

    def logout(self) -> None:
        """Đăng xuất và quay về màn hình đăng nhập."""
        self.is_authenticated = False
        SystemLogRepository.log("INFO", "AUTH", "Người dùng đã đăng xuất.")
        self.switch_screen("auth", mode="login")

    # ------------------------------------------------------------------
    # API biểu cảm trực tiếp — gọi từ bất kỳ thread nào (thread-safe)
    # ------------------------------------------------------------------

    def set_face_state(self, state: str) -> None:
        with self._state_lock:
            self._pending_state = state.strip().upper()

    def _apply_pending_state(self) -> None:
        """Đọc và áp dụng biểu cảm đang chờ vào FaceScreen (chỉ gọi từ main thread)."""
        with self._state_lock:
            state = self._pending_state
            self._pending_state = None

        if state is None:
            return

        face_scr = self.screens.get("face")
        if isinstance(face_scr, FaceScreen):
            face = getattr(face_scr, "face", None)
            if face is not None and hasattr(face, "set_state"):
                face.set_state(state)

    def _start_udp_listener(self, ip: str = "0.0.0.0", port: int = 5005) -> None:
        """Lắng nghe trạng thái biểu cảm gửi qua giao thức UDP trong thread nền."""
        def _listen():
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((ip, port))
                sock.settimeout(0.5)
                print(f"[APP] UDP Listener đang lắng nghe biểu cảm tại {ip}:{port}")
                while not self._udp_stop.is_set():
                    try:
                        data, _ = sock.recvfrom(256)
                        state = data.decode("utf-8", errors="ignore").strip().upper()
                        self.set_face_state(state)
                    except socket.timeout:
                        continue
                    except Exception as err:
                        if not self._udp_stop.is_set():
                            print(f"[APP UDP ERROR] {err}")
            except OSError as e:
                # Nếu cổng 5005 đã bị chiếm bởi tiến trình khác
                print(f"[APP] Cổng UDP {port} không khả dụng ({e}) - Bỏ qua listener mạng.")
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

        listener = threading.Thread(target=_listen, daemon=True, name="AppUDPListener")
        listener.start()

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

                    kb_active = getattr(getattr(self.current_screen, "keyboard", None), "visible", False)
                    if not kb_active and self.assistive_touch.handle_event(event):
                        continue

                    if self.current_screen:
                        self.current_screen.handle_event(event)

                if not self.running:
                    break

                # Áp dụng biểu cảm được yêu cầu từ thread ngoài
                self._apply_pending_state()

                if self.current_screen:
                    self.current_screen.update()
                self.assistive_touch.update()

                if self.current_screen:
                    self.current_screen.draw(self.screen)

                kb_active = getattr(getattr(self.current_screen, "keyboard", None), "visible", False)
                if not kb_active:
                    self.assistive_touch.draw(self.screen)

                pygame.display.flip()
                self.clock.tick(self.theme.FPS)

        except KeyboardInterrupt:
            print("\n[APP] Nhận tín hiệu thoát chương trình.")
        finally:
            self.stop()

    def stop(self):
        """Dừng vòng lặp và giải phóng tài nguyên trước khi đóng pygame."""
        self.running = False
        self._udp_stop.set()

        if self.wifi and hasattr(self.wifi, "stop"):
            try:
                self.wifi.stop()
            except Exception as err:
                print(f"[WIFI] Lỗi khi dừng WifiManager: {err}")

        pygame.quit()
