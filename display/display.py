import math
import random
import sys
import time
import threading
import pygame
import socket

UDP_IP = "0.0.0.0"  
UDP_PORT = 5005

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
FPS = 30

COLOR_BG = (205, 214, 224)
COLOR_INK = (24, 26, 32)
COLOR_TEETH = (255, 255, 255)
FACE_SCALE = 2.1

VALID_STATES = ["IDLE", "ACTIVE", "LISTENING", "THINKING", "SPEAKING", "ACTING", "WAKEWORD", "SLEEP", "STANDBY"]


def lerp(a, b, t):
    return a + (b - a) * t


def get_bezier_points(p0, p1, p2, steps=20):
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0])
        y = ((1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1])
        points.append((x, y))
    return points


# ================= LỚP KHUÔN MẶT ================= 
class AnimeRobotFace:
    def __init__(self, surface):
        self.surface = surface
        self.cx = SCREEN_WIDTH // 2
        self.cy = SCREEN_HEIGHT // 2
        self.current_state = "IDLE"
        self.state_enter_time = time.monotonic() - 10.0  # Mặc định khởi động ở trạng thái ngủ chờ wakeword
        self.eye_w = 46.0
        self.eye_h = 78.0
        self.eye_spacing = 150.0
        self.blink_progress = 0.0
        self.is_blinking = False
        self.next_blink = time.monotonic() + 3.0
        self.eyebrow_lift = 0.0
        self.mouth_open = 0.0
        self.mouth_phase = 0.0
        self.breath_phase = 0.0
        self.sleep_progress = 1.0

    def s(self, value):
        return value * FACE_SCALE

    def set_state(self, state: str):
        state = state.upper()
        if state in VALID_STATES and state != self.current_state:
            self.current_state = state
            self.state_enter_time = time.monotonic()
            print(f"[FACE] Biểu cảm -> {state}")

    def update(self):
        now = time.monotonic()

        # Xác định mục tiêu ngủ (1.0) hay thức (0.0):
        # - WAKEWORD, SLEEP, STANDBY: Chắc chắn nhắm mắt ngủ
        # - ACTIVE, LISTENING, SPEAKING, THINKING, ACTING: Chắc chắn mở mắt thức
        # - IDLE: Giữ mắt mở trong 5 giây sau tương tác; nếu sau 5s không có lệnh mới thì tự ngủ chờ wakeword
        if self.current_state in ["WAKEWORD", "SLEEP", "STANDBY"]:
            target_sleep = 1.0
        elif self.current_state in ["ACTIVE", "LISTENING", "SPEAKING", "THINKING", "ACTING"]:
            target_sleep = 0.0
        elif self.current_state == "IDLE":
            if (now - self.state_enter_time) > 5.0:
                target_sleep = 1.0
            else:
                target_sleep = 0.0
        else:
            target_sleep = 0.0

        self.sleep_progress = lerp(self.sleep_progress, target_sleep, 0.12)

        # Chớp mắt: Chỉ kích hoạt khi mắt đang mở (không ngủ)
        if self.sleep_progress < 0.3:
            if now >= self.next_blink and not self.is_blinking:
                self.is_blinking = True
                self.blink_progress = 0.0
            if self.is_blinking:
                self.blink_progress += 0.16
                if self.blink_progress >= 1.0:
                    self.is_blinking = False
                    self.blink_progress = 0.0
                    self.next_blink = now + random.uniform(2.5, 5.0)
        else:
            self.is_blinking = False
            self.blink_progress = 0.0
            self.next_blink = now + random.uniform(2.5, 4.0)

        # Nhịp thở: chậm và êm hơn khi ngủ
        breath_speed = 0.025 if self.sleep_progress > 0.5 else 0.035
        self.breath_phase += breath_speed

        target_lift = 0.0
        target_open = 0.0
        if self.current_state in ["WAKEWORD", "SLEEP", "STANDBY"]:
            target_lift = 4.0  # Lông mày hạ nhẹ thư giãn khi ngủ
            target_open = 0.0
        elif self.current_state in ["IDLE", "ACTIVE"]:
            target_lift = 0.0
            target_open = 0.0
        elif self.current_state == "LISTENING":
            target_lift = -12.0
            target_open = 0.0
        elif self.current_state == "THINKING":
            target_lift = 8.0
            target_open = 0.0
        elif self.current_state == "SPEAKING":
            self.mouth_phase += 0.28
            target_open = (math.sin(self.mouth_phase) + 1.0) * 8.0
            target_lift = (math.sin(self.mouth_phase * 0.5) * 4.0)
        elif self.current_state == "ACTING":
            target_lift = -6.0
            target_open = 0.0
        self.eyebrow_lift = lerp(self.eyebrow_lift, target_lift, 0.2)
        self.mouth_open = lerp(self.mouth_open, target_open, 0.3)

    def draw_eyebrows(self, center_y):
        brow_y = center_y - self.s(68) + self.s(self.eyebrow_lift)
        p0_l = (self.cx - self.s(110), brow_y + self.s(10))
        p1_l = (self.cx - self.s(75), brow_y - self.s(18))
        p2_l = (self.cx - self.s(38), brow_y + self.s(2))
        pts_left = get_bezier_points(p0_l, p1_l, p2_l)
        pygame.draw.lines(self.surface, COLOR_INK, False, pts_left, max(1, int(self.s(8))))
        pygame.draw.circle(self.surface, COLOR_INK, (int(p0_l[0]), int(p0_l[1])), int(self.s(4)))
        pygame.draw.circle(self.surface, COLOR_INK, (int(p2_l[0]), int(p2_l[1])), int(self.s(4)))
        p0_r = (self.cx + self.s(38), brow_y + self.s(2))
        p1_r = (self.cx + self.s(75), brow_y - self.s(18))
        p2_r = (self.cx + self.s(110), brow_y + self.s(10))
        pts_right = get_bezier_points(p0_r, p1_r, p2_r)
        pygame.draw.lines(self.surface, COLOR_INK, False, pts_right, max(1, int(self.s(8))))
        pygame.draw.circle(self.surface, COLOR_INK, (int(p0_r[0]), int(p0_r[1])), int(self.s(4)))
        pygame.draw.circle(self.surface, COLOR_INK, (int(p2_r[0]), int(p2_r[1])), int(self.s(4)))

    def draw_eyes(self, center_y):
        eye_w = self.s(self.eye_w)
        spacing = self.s(self.eye_spacing)
        lx = self.cx - spacing / 2
        rx = self.cx + spacing / 2

        if self.sleep_progress > 0.35:
            # Vẽ mắt nhắm như đang ngủ (vòng cung cong mềm mại ︶ ︶)
            t = min(1.0, (self.sleep_progress - 0.35) / 0.65)
            arc_w = eye_w * 1.15
            arc_depth = self.s(13.0) * t
            base_y = center_y + self.s(4.0)

            line_w = max(1, int(self.s(8.0)))
            cap_r = int(self.s(4.0))

            # Mắt trái
            p0_el = (lx - arc_w / 2, base_y - self.s(4.0) * t)
            p1_el = (lx, base_y + arc_depth)
            p2_el = (lx + arc_w / 2, base_y - self.s(4.0) * t)
            pts_el = get_bezier_points(p0_el, p1_el, p2_el, 20)
            pygame.draw.lines(self.surface, COLOR_INK, False, pts_el, line_w)
            pygame.draw.circle(self.surface, COLOR_INK, (int(p0_el[0]), int(p0_el[1])), cap_r)
            pygame.draw.circle(self.surface, COLOR_INK, (int(p2_el[0]), int(p2_el[1])), cap_r)

            # Mắt phải
            p0_er = (rx - arc_w / 2, base_y - self.s(4.0) * t)
            p1_er = (rx, base_y + arc_depth)
            p2_er = (rx + arc_w / 2, base_y - self.s(4.0) * t)
            pts_er = get_bezier_points(p0_er, p1_er, p2_er, 20)
            pygame.draw.lines(self.surface, COLOR_INK, False, pts_er, line_w)
            pygame.draw.circle(self.surface, COLOR_INK, (int(p0_er[0]), int(p0_er[1])), cap_r)
            pygame.draw.circle(self.surface, COLOR_INK, (int(p2_er[0]), int(p2_er[1])), cap_r)
        else:
            # Mắt mở bình thường (kèm hiệu ứng chớp mắt)
            h = self.s(self.eye_h) * (1.0 - self.sleep_progress * 1.6)
            if self.is_blinking:
                factor = abs(self.blink_progress - 0.5) * 2.0
                h = max(self.s(6), self.s(self.eye_h) * factor)
            h = max(self.s(6), h)

            left_x = lx - eye_w / 2
            right_x = rx - eye_w / 2
            y = center_y - h / 2
            radius = int(eye_w / 2)
            rect_l = pygame.Rect(int(left_x), int(y), int(eye_w), int(h))
            rect_r = pygame.Rect(int(right_x), int(y), int(eye_w), int(h))
            pygame.draw.rect(self.surface, COLOR_INK, rect_l, border_radius=radius)
            pygame.draw.rect(self.surface, COLOR_INK, rect_r, border_radius=radius)

    def draw_blush(self, center_y):
        blush_y = center_y + self.s(46)
        dy = self.s(20)
        dx = self.s(7)
        line_width = max(1, int(self.s(6)))
        lx = self.cx - self.s(120)
        pygame.draw.line(self.surface, COLOR_INK, (lx - self.s(12), blush_y - dy / 2), (lx - self.s(12) + dx, blush_y + dy / 2), line_width)
        pygame.draw.line(self.surface, COLOR_INK, (lx + self.s(4), blush_y - dy / 2), (lx + self.s(4) + dx, blush_y + dy / 2), line_width)
        rx = self.cx + self.s(120)
        pygame.draw.line(self.surface, COLOR_INK, (rx - self.s(4), blush_y - dy / 2), (rx - self.s(4) + dx, blush_y + dy / 2), line_width)
        pygame.draw.line(self.surface, COLOR_INK, (rx + self.s(12), blush_y - dy / 2), (rx + self.s(12) + dx, blush_y + dy / 2), line_width)

    def draw_mouth(self, center_y):
        mouth_y = center_y + self.s(68)

        if self.mouth_open > 1.5:
            open_factor = min(1.0, max(0.1, self.mouth_open / 16.0))
            mouth_w = self.s(96.0)
            open_h = self.s(8.0 + open_factor * 26.0)
            y_top = mouth_y - self.s(3.0)

            # Khung miệng (môi trên và môi dưới)
            p0_top = (self.cx - mouth_w / 2, y_top)
            p1_top = (self.cx, y_top + self.s(2.5))
            p2_top = (self.cx + mouth_w / 2, y_top)
            top_pts = get_bezier_points(p0_top, p1_top, p2_top, 24)

            p0_bot = (self.cx + mouth_w / 2, y_top)
            p1_bot = (self.cx, y_top + open_h * 1.35)
            p2_bot = (self.cx - mouth_w / 2, y_top)
            bottom_pts = get_bezier_points(p0_bot, p1_bot, p2_bot, 28)

            mouth_poly = top_pts + bottom_pts[1:]
            pygame.draw.polygon(self.surface, COLOR_INK, mouth_poly)

            # Răng (Teeth)
            rx = self.cx + mouth_w / 2
            lx = self.cx - mouth_w / 2
            tooth_w = self.s(16.0)
            gap = self.s(3.0)
            tooth_depth = min(open_h * 0.45, self.s(12.5))
            taper_depth = tooth_depth * 0.45
            r = self.s(3.5)

            p_r_corner = (rx - self.s(5), y_top + self.s(3))
            p_r_out = (self.cx + gap / 2 + tooth_w, y_top + taper_depth)

            p_rt_b1 = (self.cx + gap / 2 + tooth_w, y_top + tooth_depth - r)
            p_rt_c1 = (self.cx + gap / 2 + tooth_w, y_top + tooth_depth)
            p_rt_b2 = (self.cx + gap / 2 + tooth_w - r, y_top + tooth_depth)
            p_rt_b3 = (self.cx + gap / 2 + r, y_top + tooth_depth)
            p_rt_c2 = (self.cx + gap / 2, y_top + tooth_depth)
            p_rt_b4 = (self.cx + gap / 2, y_top + tooth_depth - r)

            p_notch = (self.cx, y_top + tooth_depth * 0.25)

            p_lt_b4 = (self.cx - gap / 2, y_top + tooth_depth - r)
            p_lt_c2 = (self.cx - gap / 2, y_top + tooth_depth)
            p_lt_b3 = (self.cx - gap / 2 - r, y_top + tooth_depth)
            p_lt_b2 = (self.cx - gap / 2 - tooth_w + r, y_top + tooth_depth)
            p_lt_c1 = (self.cx - gap / 2 - tooth_w, y_top + tooth_depth)
            p_lt_b1 = (self.cx - gap / 2 - tooth_w, y_top + tooth_depth - r)

            p_l_out = (self.cx - gap / 2 - tooth_w, y_top + taper_depth)
            p_l_corner = (lx + self.s(5), y_top + self.s(3))

            pts_rt_corner1 = get_bezier_points(p_rt_b1, p_rt_c1, p_rt_b2, 6)
            pts_rt_corner2 = get_bezier_points(p_rt_b3, p_rt_c2, p_rt_b4, 6)
            pts_lt_corner2 = get_bezier_points(p_lt_b4, p_lt_c2, p_lt_b3, 6)
            pts_lt_corner1 = get_bezier_points(p_lt_b2, p_lt_c1, p_lt_b1, 6)

            teeth_bot_pts = (
                [p_r_corner, p_r_out] +
                pts_rt_corner1 + pts_rt_corner2 +
                [p_notch] +
                pts_lt_corner2 + pts_lt_corner1 +
                [p_l_out, p_l_corner]
            )
            teeth_poly = top_pts + teeth_bot_pts
            pygame.draw.polygon(self.surface, COLOR_TEETH, teeth_poly)

            # Viền sắc nét cho khuôn miệng
            line_w = max(1, int(self.s(4.5)))
            pygame.draw.lines(self.surface, COLOR_INK, False, top_pts, line_w)
            pygame.draw.lines(self.surface, COLOR_INK, False, bottom_pts, line_w)
            pygame.draw.circle(self.surface, COLOR_INK, (int(self.cx - mouth_w / 2), int(y_top)), int(self.s(2.5)))
            pygame.draw.circle(self.surface, COLOR_INK, (int(self.cx + mouth_w / 2), int(y_top)), int(self.s(2.5)))
        else:
            width = self.s(64)
            pts = []
            steps = 24
            for i in range(steps + 1):
                x = (self.cx - width / 2 + (i / steps) * width)
                angle = (i / steps) * 2 * math.pi
                y = (mouth_y + math.sin(angle) * self.s(5.5))
                pts.append((x, y))
            pygame.draw.lines(self.surface, COLOR_INK, False, pts, max(1, int(self.s(6))))
            pygame.draw.circle(self.surface, COLOR_INK, (int(pts[0][0]), int(pts[0][1])), int(self.s(3)))
            pygame.draw.circle(self.surface, COLOR_INK, (int(pts[-1][0]), int(pts[-1][1])), int(self.s(3)))

    def draw(self):
        self.surface.fill(COLOR_BG)
        center_y = (self.cy + math.sin(self.breath_phase) * self.s(3.0))
        self.draw_eyebrows(center_y)
        self.draw_eyes(center_y)
        self.draw_blush(center_y)
        self.draw_mouth(center_y)


def udp_listener(face: "AnimeRobotFace", stop_event: threading.Event):
    """Chạy trong thread riêng, lắng nghe UDP liên tục, cập nhật state."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.5)  # Timeout ngắn để kiểm tra stop_event
    
    print(f"[UDP] Đang lắng nghe dữ liệu biểu cảm tại cổng {UDP_PORT}")
    
    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(1024)  # Nhận gói tin
            state = data.decode("utf-8", errors="ignore").strip().upper()
            face.set_state(state)
        except socket.timeout:
            continue  # Hết 0.5s không có data thì lặp lại để check stop_event
        except Exception as e:
            print(f"[UDP ERROR] {e}")

    sock.close()


# ================= MAIN =================
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
    pygame.display.set_caption("BD-1 Robot Face")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    face = AnimeRobotFace(screen)

    stop_event = threading.Event()
    listener_thread = threading.Thread(target=udp_listener, args=(face, stop_event), daemon=True)
    listener_thread.start()

    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            face.update()
            face.draw()
            pygame.display.flip()
            clock.tick(FPS)
    except KeyboardInterrupt:
        print("\n[FACE] Đã nhận tín hiệu dừng (Ctrl+C).")
    finally:
        stop_event.set()
        listener_thread.join(timeout=2)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    main()
