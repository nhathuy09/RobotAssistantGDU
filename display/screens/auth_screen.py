import pygame
from typing import Optional
import hashlib
from display.screens.base_screen import BaseScreen
from display.components.button import Button
from display.components.card import Card
from display.components.input_field import InputField
from display.components.virtual_keyboard import VirtualKeyboard
from display.theme import Colors, Theme
from database.repositories import AdminRepository, SystemLogRepository

class AuthScreen(BaseScreen):
    PAGE_BG = Colors.PAGE_BG
    CARD_BG = Colors.CARD_BG
    CARD_BORDER = Colors.CARD_BORDER
    INPUT_BG = Colors.INPUT_BG
    INPUT_BORDER = Colors.INPUT_BORDER
    INPUT_FOCUS = Colors.INPUT_FOCUS
    INPUT_PLACEHOLDER = Colors.INPUT_PLACEHOLDER
    BTN_BG = Colors.BTN_BG
    BTN_HOVER = Colors.BTN_HOVER
    TEXT_MAIN = Colors.TEXT_MAIN
    TEXT_MUTED = Colors.TEXT_MUTED
    TEXT_FOOTER = Colors.TEXT_FOOTER
    ERROR_COLOR = Colors.ERROR_COLOR
    SUCCESS_COLOR = Colors.SUCCESS_COLOR

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.mode = "login"
        self.message = ""

        # Card trung tâm
        self.card_rect = pygame.Rect(165, 35, 470, 410)
        self.card = Card(
            rect=self.card_rect,
            theme=self.theme,
            bg_color=self.CARD_BG,
            border_color=self.CARD_BORDER,
            border_radius=24,
        )

        field_x = self.card_rect.x + 36
        field_w = self.card_rect.width - 72  # 398px

        # Input 1: Username
        self.input_username = InputField(
            rect=pygame.Rect(field_x, 150, field_w, 46),
            placeholder="Enter a username",
            theme=self.theme,
            font=self.theme.get_font(15),
            max_length=32,
        )
        self._style_input(self.input_username)

        # Input 2: Password
        self.input_password = InputField(
            rect=pygame.Rect(field_x, 230, field_w, 46),
            placeholder="Enter a password or PIN",
            theme=self.theme,
            font=self.theme.get_font(15),
            is_password=True,
            has_eye_toggle=True,
            max_length=64,
        )
        self._style_input(self.input_password)

        # Input 3: PIN (chỉ dùng khi đăng ký, bắt buộc đúng 6 số)
        self.input_pin = InputField(
            rect=pygame.Rect(field_x, 260, field_w, 42),
            placeholder="Enter a 6-digit PIN",
            theme=self.theme,
            font=self.theme.get_font(15),
            is_password=True,
            has_eye_toggle=True,
            is_numeric=True,
            max_length=6,
            visible=False,
        )
        self._style_input(self.input_pin)

        # Nút chính (Action Button)
        self.btn_submit = Button(
            rect=pygame.Rect(field_x, 302, field_w, 48),
            text="Sign In & Continue",
            theme=self.theme,
            font=self.theme.get_font(16, bold=True),
            bg_color=self.BTN_BG,
            fg_color=(255, 255, 255),
            border_color=self.BTN_BG,
            border_radius=12,
            on_click=self._on_submit,
            primary=True,
        )

        # Vùng click link chuyển mode (ở dưới footer)
        self.switch_rect = pygame.Rect(self.card_rect.x, 370, self.card_rect.width, 26)

        # Nút đăng xuất khi đã đăng nhập
        self.back_btn_rect = pygame.Rect(18, 16, 96, 36)
        self.btn_logout = Button(
            rect=pygame.Rect(18, 16, 96, 34),
            text="Đăng xuất",
            theme=self.theme,
            font=self.theme.get_font(13, bold=True),
            bg_color=(235, 232, 224),
            fg_color=self.TEXT_MAIN,
            border_color=(220, 216, 208),
            border_radius=10,
            primary=False,
            on_click=self._on_logout,
        )

        # Bàn phím ảo cảm ứng (Virtual Keyboard)
        self.keyboard = VirtualKeyboard(
            top_y=230,
            height=250,
            width=800,
            on_submit=self._on_keyboard_submit,
            on_cancel=self._on_keyboard_cancel,
        )

    def _style_input(self, field: InputField):
        field.bg_color = self.INPUT_BG
        field.border_color = self.INPUT_BORDER
        field.focus_color = self.INPUT_FOCUS
        field.text_color = self.TEXT_MAIN
        field.placeholder_color = self.INPUT_PLACEHOLDER
        field.border_radius = 12
        field.padding = 14

    @staticmethod
    def _hash_value(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def on_enter(self, mode: str = "login", **kwargs):
        self.mode = mode if mode in ["login", "register"] else "login"
        self.message = ""
        self.input_username.value = ""
        self.input_password.value = ""
        self.input_pin.value = ""
        self.keyboard.close()
        self.input_username.set_focus(False)
        self.input_password.set_focus(False)
        self.input_pin.set_focus(False)
        self._update_layout()
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def on_leave(self):
        self.keyboard.close()
        self._update_layout()
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self.message = ""
        self.keyboard.close()
        self.input_username.set_focus(False)
        self.input_password.set_focus(False)
        self.input_pin.set_focus(False)
        self._update_layout()

    def _get_shift_y(self) -> int:
        if not getattr(self, "keyboard", None) or not self.keyboard.visible:
            return 0
        active = self.keyboard.active_input
        if self.mode == "register":
            if active is self.input_username:
                return 40
            elif active is self.input_password:
                return 85
            elif active is self.input_pin:
                return 155
        else:
            if active is self.input_username:
                return 50
            elif active is self.input_password:
                return 115
        return 0

    def _update_layout(self):
        shift_y = self._get_shift_y()
        field_x = 201
        field_w = 398

        if self.mode == "login":
            base_top = 35 - shift_y
            self.card_rect = pygame.Rect(165, base_top, 470, 410)
            self.card.rect = self.card_rect

            self.input_username.rect = pygame.Rect(field_x, base_top + 120, field_w, 46)
            self.input_username.placeholder = "Enter a username"

            self.input_password.rect = pygame.Rect(field_x, base_top + 198, field_w, 46)
            self.input_password.placeholder = "Enter a password or PIN"

            self.input_pin.visible = False

            self.btn_submit.rect = pygame.Rect(field_x, base_top + 265, field_w, 48)
            self.btn_submit.text = "Sign In & Continue"

            self.switch_rect = pygame.Rect(self.card_rect.x, base_top + 348, self.card_rect.width, 24)
        else:
            # Chế độ Register: 3 fields (Username, Password, PIN)
            base_top = 15 - shift_y
            self.card_rect = pygame.Rect(165, base_top, 470, 450)
            self.card.rect = self.card_rect

            self.input_username.rect = pygame.Rect(field_x, base_top + 98, field_w, 42)
            self.input_username.placeholder = "Enter a username"

            self.input_password.rect = pygame.Rect(field_x, base_top + 168, field_w, 42)
            self.input_password.placeholder = "Enter a password (min 6 chars)"

            self.input_pin.rect = pygame.Rect(field_x, base_top + 238, field_w, 42)
            self.input_pin.placeholder = "Enter a 6-digit PIN"
            self.input_pin.visible = True

            self.btn_submit.rect = pygame.Rect(field_x, base_top + 301, field_w, 46)
            self.btn_submit.text = "Register & Continue"

            self.switch_rect = pygame.Rect(self.card_rect.x, base_top + 382, self.card_rect.width, 24)

    def _open_keyboard_for(self, field: InputField):
        """Mở bàn phím ảo cho trường nhập tương ứng."""
        self.keyboard.open(target_input=field)
        self.keyboard.is_numeric = (field is self.input_pin)
        self._update_layout()

    def _on_keyboard_submit(self):
        """Khi bấm Xong trên bàn phím ảo."""
        active = self.keyboard.active_input
        if active is self.input_username:
            self.input_username.set_focus(False)
            self.input_password.set_focus(True)
            self._open_keyboard_for(self.input_password)
        elif active is self.input_password:
            if self.mode == "register":
                self.input_password.set_focus(False)
                self.input_pin.set_focus(True)
                self._open_keyboard_for(self.input_pin)
            else:
                self.keyboard.close()
                self._update_layout()
                self._on_submit()
        elif active is self.input_pin:
            pin = self.input_pin.value.strip()
            if not pin.isdigit() or len(pin) != 6:
                self.message = f"Mã PIN bắt buộc phải đủ đúng 6 chữ số (hiện có {len(pin)}/6 số)."
                return
            self.keyboard.close()
            self._update_layout()
            self._on_submit()
        else:
            self.keyboard.close()
            self._update_layout()

    def _on_keyboard_cancel(self):
        self.keyboard.close()
        self._update_layout()

    def _on_submit(self):
        username = self.input_username.value.strip()
        secret = self.input_password.value.strip()
        pin = self.input_pin.value.strip()
        if not username:
            self.message = "Vui lòng nhập tên đăng nhập."
            self.input_username.set_focus(True)
            self._open_keyboard_for(self.input_username)
            return

        if not secret:
            self.message = "Vui lòng nhập mật khẩu."
            self.input_password.set_focus(True)
            self._open_keyboard_for(self.input_password)
            return

        settings = self.app_manager.settings
        admin = settings.get("admin")

        if self.mode == "register":
            if len(secret) < 6:
                self.message = "Mật khẩu phải có ít nhất 6 ký tự."
                self.input_password.set_focus(True)
                self._open_keyboard_for(self.input_password)
                return

            if not pin.isdigit() or len(pin) != 6:
                self.message = f"Mã PIN bắt buộc phải đủ đúng 6 chữ số (hiện có {len(pin)}/6 số)."
                self.input_pin.set_focus(True)
                self._open_keyboard_for(self.input_pin)
                return

            if AdminRepository.is_registered():
                self.message = "Tài khoản quản trị đã tồn tại."
                return

            AdminRepository.create_or_update_admin(
                username, self._hash_value(secret), self._hash_value(pin)
            )
            self.app_manager.settings["admin"] = {
                "username": username,
                "password_hash": self._hash_value(secret),
                "pin_hash": self._hash_value(pin),
            }
            self.app_manager.persist_settings()
            SystemLogRepository.log("OK", "AUTH", f"Đã đăng ký tài khoản admin '{username}' vào DB thành công.")
            self.message = "Đăng ký thành công! Đang đăng nhập..."
            self.app_manager.login()
            return

        # Login mode
        admin = AdminRepository.get_admin()
        if not admin:
            self.message = "Chưa có tài khoản. Vui lòng đăng ký."
            self.mode = "register"
            self._update_layout()
            return

        hash_secret = self._hash_value(secret)
        valid_creds = (
            username == admin.get("username")
            and (hash_secret == admin.get("password_hash") or hash_secret == admin.get("pin_hash"))
        )

        if not valid_creds:
            self.message = "Tên đăng nhập hoặc mật khẩu / PIN không đúng."
            SystemLogRepository.log("WARN", "AUTH", f"Đăng nhập thất bại: user '{username}'.")
            self.input_password.set_focus(True)
            self._open_keyboard_for(self.input_password)
            return

        self.message = "Đăng nhập thành công."
        SystemLogRepository.log("OK", "AUTH", f"Admin '{username}' đăng nhập thành công.")
        self.app_manager.login()

    def _on_logout(self):
        self.app_manager.logout()

    def _get_active_fields(self):
        if self.mode == "register":
            return [self.input_username, self.input_password, self.input_pin]
        return [self.input_username, self.input_password]

    def handle_event(self, event: pygame.event.Event) -> bool:
        fields = self._get_active_fields()

        # Khi bàn phím ảo đang mở
        if self.keyboard.visible:
            # 1. Bàn phím ảo nhận event
            if self.keyboard.handle_event(event):
                return True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Click con mắt ẩn/hiện mật khẩu
                for field in fields:
                    if field.has_eye_toggle and field.eye_rect.collidepoint(event.pos):
                        field.show_password = not field.show_password
                        return True

                # Click chuyển sang ô input khác
                for field in fields:
                    if field.rect.collidepoint(event.pos):
                        for other in fields:
                            other.set_focus(other is field)
                        self._open_keyboard_for(field)
                        return True

                # Click nút submit
                if self.btn_submit.handle_event(event):
                    self.keyboard.close()
                    self._update_layout()
                    return True

                # Chạm ngoài vùng bàn phím (vùng trống phía trên) -> đóng bàn phím
                if event.pos[1] < self.keyboard.rect.y:
                    self.keyboard.close()
                    for f in fields:
                        f.set_focus(False)
                    self._update_layout()
                    return True

            # Gõ phím vật lý khi bàn phím đang mở
            for field in fields:
                if field.focused and field.handle_event(event):
                    return True
            return False

        # Khi bàn phím chưa mở
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            current_index = next((i for i, f in enumerate(fields) if f.focused), -1)
            next_index = (current_index + 1) % len(fields)
            for f in fields:
                f.set_focus(False)
            fields[next_index].set_focus(True)
            self._open_keyboard_for(fields[next_index])
            return True
        if event.type ==pygame.KEYDOWN and event.key==pygame.K_TAB:
            if self.mode=="login":
                self.input_username.set_focus(True),self.input_password.set_focus()==self.input_password.set_focus(),self.input_username.set_focus()
            else:
                if self.input_username.set_focus(True):
                    self.input_username.set_focus(False)
                    self.input_password.set_focus(True)
                elif self.input_password.set_focus(True):
                    self.input_password.set_focus(False)
                    self.input_pin.set_focus(True)
                elif self.input_pin.set_focus(True):
                    self.input_pin.set_focus(False)
                    self.input_username.set_focus(True)  
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Nút đăng xuất khi đã xác thực
            if getattr(self.app_manager, "is_authenticated", False):
                if self.btn_logout.handle_event(event):
                    return True
                # Nút quay lại màn hình khuôn mặt
                if self.back_btn_rect.collidepoint(event.pos):
                    self.app_manager.switch_screen("face")
                    return True

            # Click vào link chuyển đổi mode
            if self.switch_rect.collidepoint(event.pos):
                self._toggle_mode()
                return True

            # Click vào ô nhập liệu -> mở bàn phím ảo ngay lập tức!
            for field in fields:
                if field.has_eye_toggle and field.eye_rect.collidepoint(event.pos):
                    field.show_password = not field.show_password
                    for other in fields:
                        other.set_focus(other is field)
                    self._open_keyboard_for(field)
                    return True

                if field.rect.collidepoint(event.pos):
                    for other in fields:
                        other.set_focus(other is field)
                    self._open_keyboard_for(field)
                    return True

            for field in fields:
                field.set_focus(False)

        # Chuyển event gõ phím vật lý vào field đang focus
        for field in fields:
            if field.focused and field.handle_event(event):
                return True

        if self.btn_submit.handle_event(event):
            return True

        return False

    def update(self):
        self.input_username.update()
        self.input_password.update()
        if self.mode == "register":
            self.input_pin.update()
        if self.keyboard.visible:
            self.keyboard.update()

    def _draw_lock_icon(self, surface: pygame.Surface, cx: int, cy: int, color):
        """Vẽ biểu tượng ổ khóa vector tinh xảo giống hình mẫu."""
        body_rect = pygame.Rect(cx - 6, cy - 2, 12, 10)
        pygame.draw.rect(surface, color, body_rect, width=1, border_radius=2)
        pygame.draw.arc(surface, color, (cx - 4, cy - 8, 8, 8), 0, 3.14159, 1)
        pygame.draw.line(surface, color, (cx - 4, cy - 4), (cx - 4, cy - 2), 1)
        pygame.draw.line(surface, color, (cx + 4, cy - 4), (cx + 4, cy - 2), 1)
        pygame.draw.circle(surface, color, (cx, cy + 2), 1)

    def draw(self, surface: pygame.Surface):
        # 1. Nền ấm mượt toàn màn hình
        surface.fill(self.PAGE_BG)

        is_auth = getattr(self.app_manager, "is_authenticated", False)
        if is_auth:
            self.btn_logout.draw(surface)
            back_surf = self.theme.get_font(13, bold=True).render("← Quay lại", True, self.TEXT_MUTED)
            surface.blit(back_surf, (126, 24))

        # 2. Vẽ Card chứa form ở trung tâm
        self.card.draw(surface)

        top = self.card_rect.y
        cx = self.card_rect.centerx

        # 3. Tiêu đề và Phụ đề
        if self.mode == "register":
            title_text = "Create Admin Account"
            subtitle_text = "Set up your access to this robot's controls."
            title_y = top + 18
            subtitle_y = top + 46
        else:
            title_text = "Admin Login"
            subtitle_text = "Sign in to access this robot's controls."
            title_y = top + 26
            subtitle_y = top + 58

        title_surf = self.theme.get_font(24, bold=True).render(title_text, True, self.TEXT_MAIN)
        subtitle_surf = self.theme.get_font(14).render(subtitle_text, True, self.TEXT_MUTED)

        surface.blit(title_surf, (cx - title_surf.get_width() // 2, title_y))
        surface.blit(subtitle_surf, (cx - subtitle_surf.get_width() // 2, subtitle_y))

        # 4. Trường nhập liệu và Nhãn
        if self.mode == "register":
            # 3 trường: Username, Password, PIN
            lbl_user = self.theme.get_font(14, bold=True).render("Username", True, self.TEXT_MAIN)
            surface.blit(lbl_user, (self.input_username.rect.x, self.input_username.rect.y - 20))
            self.input_username.draw(surface)

            lbl_pass = self.theme.get_font(14, bold=True).render("Password", True, self.TEXT_MAIN)
            surface.blit(lbl_pass, (self.input_password.rect.x, self.input_password.rect.y - 20))
            self.input_password.draw(surface)

            pin_len = len(self.input_pin.value)
            pin_lbl_text = f"Security PIN (bắt buộc đúng 6 số) • {pin_len}/6"
            pin_col = self.SUCCESS_COLOR if pin_len == 6 else (self.ERROR_COLOR if pin_len > 0 else self.TEXT_MAIN)
            lbl_pin = self.theme.get_font(13, bold=True).render(pin_lbl_text, True, pin_col)
            surface.blit(lbl_pin, (self.input_pin.rect.x, self.input_pin.rect.y - 20))
            self.input_pin.draw(surface)
        else:
            # 2 trường: Username, Password / PIN (ẩn ô PIN)
            lbl_user = self.theme.get_font(14, bold=True).render("Username", True, self.TEXT_MAIN)
            surface.blit(lbl_user, (self.input_username.rect.x, self.input_username.rect.y - 22))
            self.input_username.draw(surface)

            lbl_pass = self.theme.get_font(14, bold=True).render("Password / PIN", True, self.TEXT_MAIN)
            surface.blit(lbl_pass, (self.input_password.rect.x, self.input_password.rect.y - 22))
            self.input_password.draw(surface)

        # 5. Nút Action
        self.btn_submit.draw(surface)

        # 6. Chân Card: Icon ổ khóa + "Admin access for this robot."
        footer_text = "Admin access for this robot."
        footer_surf = self.theme.get_font(13).render(footer_text, True, self.TEXT_FOOTER)

        if self.mode == "register":
            lock_cy = top + 360
            link_y = top + 384
        else:
            lock_cy = top + 328
            link_y = top + 352

        lock_cx = cx - footer_surf.get_width() // 2 - 10
        self._draw_lock_icon(surface, lock_cx, lock_cy, self.TEXT_FOOTER)
        surface.blit(footer_surf, (lock_cx + 10, lock_cy - footer_surf.get_height() // 2))

        # 7. Link chuyển mode nhỏ gọn ở dưới cùng card
        if self.mode == "login":
            switch_text = "Need an admin account? Register"
        else:
            switch_text = "Already have an account? Sign In"

        mouse_pos = pygame.mouse.get_pos()
        hover_switch = self.switch_rect.collidepoint(mouse_pos)
        switch_color = self.INPUT_FOCUS if hover_switch else self.TEXT_MUTED
        switch_surf = self.theme.get_font(12).render(switch_text, True, switch_color)
        surface.blit(switch_surf, (cx - switch_surf.get_width() // 2, link_y))

        # 8. Thông báo lỗi hoặc thành công (Toast / Alert)
        if self.message:
            error_keywords = ("vui lòng", "không đúng", "chưa có", "phải", "tồn tại", "lỗi")
            is_error = any(k in self.message.lower() for k in error_keywords)
            msg_color = self.ERROR_COLOR if is_error else self.SUCCESS_COLOR
            msg_surf = self.theme.get_font(13, bold=True).render(self.message, True, msg_color)
            
            alert_y = top + 70 if self.mode == "register" else top + 84
            surface.blit(msg_surf, (cx - msg_surf.get_width() // 2, alert_y))

        # 9. Bàn phím ảo cảm ứng (vẽ đè lên nửa dưới khi được mở)
        if self.keyboard.visible:
            self.keyboard.draw(surface)