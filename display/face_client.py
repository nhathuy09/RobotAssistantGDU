import socket
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from display.app_manager import AppManager


class FaceClient:
    """Client gửi trạng thái biểu cảm tới giao diện hiển thị (FaceScreen).
    
    Hỗ trợ 2 chế độ:
    1. Trực tiếp qua AppManager (In-memory, Zero-latency, Thread-safe).
    2. Qua mạng UDP socket (dành cho chế độ chạy riêng biệt nhiều tiến trình).
    """

    VALID_STATES = frozenset([
        "IDLE", "ACTIVE", "LISTENING", "THINKING",
        "SPEAKING", "ACTING", "WAKEWORD", "SLEEP", "STANDBY",
    ])

    def __init__(self, app_manager: Optional["AppManager"] = None, ip: str = "127.0.0.1", port: int = 5005):
        self._app = app_manager
        self.ip = ip
        self.port = port
        self.sock: Optional[socket.socket] = None

        if self._app is not None:
            print("[FACE] Khởi tạo FaceClient chế độ trực tiếp (In-memory AppManager).")
        else:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.resolved_ip = socket.gethostbyname(ip)
                print(f"[FACE] Khởi tạo FaceClient chế độ mạng UDP -> {self.resolved_ip}:{self.port}")
            except Exception as e:
                print(f"[FACE] Cảnh báo lỗi phân giải UDP {ip} ({e}).")

    def send_state(self, state: str) -> None:
        normalized = state.strip().upper()
        if normalized not in self.VALID_STATES:
            return

        if self._app is not None:
            try:
                self._app.set_face_state(normalized)
            except Exception as e:
                print(f"[FACE] Lỗi cập nhật biểu cảm AppManager: {e}")
            return

        if not self.sock:
            return
        try:
            self.sock.sendto(normalized.encode("utf-8"), (self.ip, self.port))
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"[FACE] Lỗi gửi UDP: {e}")

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None