import pygame
from typing import Optional
import hashlib
from display.components.base_widget import BaseWidget
from display.screens.base_screen import BaseScreen
from display.components.button import Button
from display.components.card import Card
from display.components.input_field import InputField
from display.theme import Colors, Theme

class AuthScreen(BaseScreen):
    def __init__(self,app_manager):
        super().__init__(app_manager)
        self.mode="login"
        self.message=""
        self.card =Card(
            rect=pygame.Rect(85, 30, 630, 420),
            theme=self.theme,
            bg_color=Colors.CARD_BG,
            border_color=Colors.CARD_BORDER,
            border_radius=20,
        )
        self.input_username=InputField(
            rect=pygame.Rect(120, 140, 560, 52),
            placeholder="Nhập tên đăng nhập",
            theme=self.theme,
            font=self.theme.get_font(20),
            max_length=32,
        )
        self.input_password=InputField(
            rect=pygame.Rect(120, 226, 560, 52),
            placeholder="Nhập mật khẩu",
            theme=self.theme,
            font=self.theme.get_font(20),
            is_password=True,
            max_length=64,
            has_eye_toggle=True,)
        self.input_pin=InputField(
            rect=pygame.Rect(120, 312, 560, 52),
            placeholder="Nhập mã PIN",
            theme=self.theme,
            font=self.theme.get_font(20),
            is_password=True,
            has_eye_toggle=True,
            max_length=12,
            is_numeric=True,)
        self.btn_submit=Button(
            rect=pygame.Rect(120, 310, 560, 50),
            text="Đăng nhập",
            theme=self.theme,
            font=self.theme.get_font(20, bold=True),
            on_click=self._on_submit,
            primary=True,
        )
        self.btn_switch_mode=Button(
            rect=pygame.Rect(260, 372, 280, 36),
            text="Chưa có tài khoản? Đăng ký",
            theme=self.theme,
            font=self.theme.get_font(16),
           
            primary=False,
            bg_color=Colors.CARD_BG,
            fg_color=Colors.BTN_PRIMARY,
            border_color=Colors.CARD_BG,
            on_click=self._toggle_mode,
        )
    @staticmethod
    def _hash_value(value:str)->str:
        return hashlib.sha256(value.encode()).hexdigest()
    def on_enter(self,mode:str="login", **kwargs):
        self.mode=mode if mode in ["login","register"] else "login"
        self.message=""
        self.input_username.value=""
        self.input_password.value=""
        self.input_pin.value=""
        self.input_username.set_focus(True)
        self.input_password.set_focus(False)
        self.input_pin.set_focus(False)
        self._update_layout()
        pygame.key.start_text_input()
    def on_leave(self):
        pygame.key.stop_text_input()
    def _toggle_mode(self):
        self.mode="register" if self.mode=="login" else "login"
        self.message=""
        self.input_username.set_focus(True)
        self.input_password.set_focus(False)
        self.input_pin.set_focus(False)
        self._update_layout()
    def _update_layout(self):
        if self.mode=="login":
            self.card.rect=pygame.Rect(85, 30, 630, 420)
            self.input_username.rect= pygame.Rect(120, 140, 560, 52)
            self.input_password.rect= pygame.Rect(120, 226, 560, 52)
            self.input_pin.visible = False
            self.btn_submit.rect= pygame.Rect(120, 310, 560, 50)
            self.btn_submit.text="Đăng nhập"
            self.btn_switch_mode.rect= pygame.Rect(260, 372, 280, 36)
            self.btn_switch_mode.text="Chưa có tài khoản? Đăng ký"
        else:
            self.card.rect = pygame.Rect(85, 15, 630, 450)
            self.input_username.rect = pygame.Rect(120, 110, 560, 48)
            self.input_password.rect = pygame.Rect(120, 186, 560, 48)
            self.input_pin.rect = pygame.Rect(120, 262, 560, 48)
            self.input_pin.visible = True
            self.btn_submit.rect = pygame.Rect(120, 338, 560, 50)
            self.btn_submit.text = "Đăng ký"
            self.btn_switch_mode.rect = pygame.Rect(260, 400, 280, 36)
            self.btn_switch_mode.text = "Đã có tài khoản? Đăng nhập"
            
    def _on_submit(self):
        username=self.input_username.value.strip()
        password=self.input_password.value.strip()
        pin=self.input_pin.value.strip()
        if not username:
            self.message="Vui lòng nhập tên đăng nhập."
            self.input_username.set_focus(True)
            return
        if not password:
            self.message="Vui lòng nhập mật khẩu."
            self.input_password.set_focus(True)
            return
        settings = self.app_manager.settings
        admin = settings.get("admin")
        
        if self.mode =="register":
            if len(password)<6:
                self.message="Mật khẩu phải có ít nhất 6 ký tự."
                self.input_password.set_focus(True)
                return
            if len(pin)<4:
                self.message="Mã PIN phải có ít nhất 4 ký tự."
                self.input_pin.set_focus(True)
                return
            if not pin.isdigit():
                self.message="Mã PIN phải là số."
                self.input_pin.set_focus(True)
                return
            if admin and admin.get("password_hash"):
                self.message="Tài khoản đã tồn tại"
                return
            settings["admin"]={
                "username":username,
                "password_hash":self._hash_value(password),
                "pin_hash":self._hash_value(pin),
            }
            self.app_manager.persist_settings()
            self.message="Tạo tài khoản thành công. Vui lòng đăng nhập."
            self.app_manager.switch_screen("auth",mode="login")
            return
        if not admin or not admin.get("password_hash"):
            self.message="Chưa có tài khoản. Vui lòng đăng ký."
            return
        if username != admin.get("username") or self._hash_value(password) != admin.get("password_hash"):
            self.message="Tên đăng nhập hoặc mật khẩu không đúng."
            return
        self.message="Đăng nhập thành công."
        self.app_manager.switch_screen("face")
        
    def handle_event(self,event:pygame.event.Event)->bool:
        if event.type==pygame.KEYDOWN and event.key == pygame.K_TAB:
            fields=[self.input_username, self.input_password]
            if self.mode=="register":
                fields.append(self.input_pin)
            current_index = next((i for i, f in enumerate(fields) if f.focused), -1)
            next_index = (current_index + 1) % len(fields)
            for field in fields:
                field.set_focus(False)
            fields[next_index].set_focus(True)
            return True
        fields = [self.input_username, self.input_password]
        if self.mode == "register":
            fields.append(self.input_pin)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for field in fields:
                hit = field.rect.collidepoint(event.pos)

                if field.has_eye_toggle:
                    hit = hit or field.eye_rect.collidepoint(event.pos)

                if hit:
                    for other in fields:
                        other.set_focus(other is field)

                    field.handle_event(event)
                    return True

            for field in fields:
                field.set_focus(False)

        # Chỉ trường đang focus nhận sự kiện nhập liệu.
        for field in fields:
            if field.focused and field.handle_event(event):
                return True

        if self.btn_submit.handle_event(event):
            return True

        if self.btn_switch_mode.handle_event(event):
            return True
        return False

    def update(self):
        self.input_username.update()
        self.input_password.update()
        if self.mode=="register":
            self.input_pin.update()
    def draw(self,surface:pygame.Surface):
        surface.fill(Colors.BG_PAGE)
        self.card.draw(surface)
        top = self.card.rect.y
        mid=self.card.rect.centerx
        
        if self.mode == "login":
            title = "Admin Login"
            subtitle = "Vui lòng đăng nhập để tiếp tục."
        else:
            title = "Tạo tài khoản quản trị"
            subtitle = "Vui lòng tạo tài khoản quản trị."

        title_surface = self.theme.get_font(24, bold=True).render(
            title, True, Colors.TEXT_DARK)
        subtitle_surface = self.theme.get_font(16).render(
            subtitle, True, Colors.TEXT_MUTED)

        surface.blit(
            title_surface,
            (mid - title_surface.get_width() // 2, top + 18),)
        surface.blit(
            subtitle_surface,
            (mid - subtitle_surface.get_width() // 2, top + 48),)

        labels = [
            ("Tên đăng nhập", self.input_username),
            ("Mật khẩu", self.input_password),
        ]

        if self.mode == "register":
            labels.append(("Mã PIN", self.input_pin))

        for label, field in labels:
            label_surface = self.theme.get_font(16).render(label, True, Colors.TEXT_DARK)
            surface.blit(label_surface,(field.rect.x, field.rect.y - 20),)
            field.draw(surface)
        self.btn_submit.draw(surface)
        self.btn_switch_mode.draw(surface)
        if self.message:
            error_keywords = (
                "vui lòng",
                "phải",
                "không chính xác",
                "chưa có",
                "đã tồn tại",
                "chỉ được",
            )

            is_error = any( keyword in self.message.lower() for keyword in error_keywords)
            color = Colors.COLOR_DANGER if is_error else Colors.GREEN_TEXT
            message_surface = self.theme.get_font(14).render(self.message, True, color)

            message_y = self.btn_switch_mode.rect.bottom + 4

            # Giữ thông báo trong giới hạn màn hình.
            max_width = self.card.rect.width - 30

            if message_surface.get_width() > max_width:
                message_surface = pygame.transform.scale(message_surface,(max_width, message_surface.get_height()),)
            surface.blit(message_surface,(mid - message_surface.get_width() // 2,min(message_y, self.card.rect.bottom - 22),),)
            