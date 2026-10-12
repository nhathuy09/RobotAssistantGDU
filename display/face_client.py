import socket

class FaceClient:
    def __init__(self, ip="127.0.0.1", port=5005):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.resolved_ip = socket.gethostbyname(ip)
            print(f"[FACE] Đã phân giải {ip} -> {self.resolved_ip}, sẵn sàng UDP.")
        except Exception as e:
            print(f"[FACE] Không thể phân giải {ip} ({e}). Tạm ngắt FaceClient để chống nghẽn mạng.")

    def send_state(self, state: str):
        if  not self.sock :
            return
        try:
            self.sock.sendto(state.strip().encode("utf-8"), (self.ip, self.port))
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"[FACE] Lỗi gửi UDP: {e}")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
    
    # def __init__(self,ip="gdupi3.local", port=5005):
    #     self.ip = ip
    #     self.port = port
    #     self.target_ip=None
    #     self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     self.sock.setblocking(False)  # Set socket to non-blocking mode
    #     self.resolve_ip()
    #     if self.target_ip:
    #         print(f"[FACE] Đã khởi tạo UDP Client bắn tới {self.target_ip}:{self.port}")
    #     else:
    #         print(f"[FACE] Không thể resolve IP: {self.ip}")
    # def resolve_ip(self):
    #     try:
    #         resolved = socket.gethostbyname(self.raw_ip)
    #         self.target_ip = resolved
    #         print(f"[FACE] Phân giải thành công {self.raw_ip} -> {self.target_ip}")
    #     except Exception as e:
    #         print(f"[FACE] Lỗi phân giải IP: {e}")
    #         self.target_ip = None
    # def send_state(self, state: str):
    #     if not self.sock or not self.target_ip:
    #         return
    #     try:
    #         payload = state.strip().encode("utf-8")
    #         self.sock.sendto(payload, (self.target_ip, self.port))
    #     except BlockingIOError:
    #         pass
    #     except Exception as e:
    #         print(f"[FACE] Lỗi gửi UDP: {e}")
    #         self.target_ip = None
    # def close(self):
    #     if self.sock:
    #         try:
    #             self.sock.close()
    #         except Exception as e:
    #             print(f"[FACE] Lỗi đóng socket: {e}")
    #         self.sock = None
            
        