import socket

class FaceClient:
    def __init__(self, ip="gdupi3.local", port=5005):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[FACE] Đã khởi tạo UDP Client bắn tới {self.ip}:{self.port}")

    def send_state(self, state: str):
        try:
            # Gửi gói tin thẳng đi, không cần chờ phản hồi
            self.sock.sendto(state.strip().encode("utf-8"), (self.ip, self.port))
        except Exception as e:
            print(f"[FACE] Lỗi gửi UDP: {e}")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None