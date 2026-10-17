import pygame
from typing import Optional
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
            bg_color=Colors.CARD_BG,
            border_color=Colors.CARD_BORDER,
            border_radius=20,
        )
        self.input_username=InputField(
            rect=pygame.Rect(120, 140, 560, 52),
            placeholder="Nhập tên đăng nhập",
            font=self.theme.get_font(20),
            max_length=32,
        )
        self.input_password=InputField(
            rect=pygame.Rect(120, 226, 560, 52),
            placeholder="Nhập mật khẩu",
            font=self.theme.get_font(20),
            is_password=True,
            max_length=64,
            has_eye_toggle=True,)
        self.input_pin=InputField(
            rect=pygame.Rect(120, 312, 560, 52),
            placeholder="Nhập mã PIN",
            font=self.theme.get_font(20),
            is_password=True,
            has_eye_toggle=True,
            max_length=12,
            is_numeric=True,)
        self.btn_submit=Button(
            rect=pygame.Rect(120, 310, 560, 50),
            text="Đăng nhập",
            font=self.theme.get_font(20, bold=True),
            on_click=self._on_submit,
            primary=True,
        )
        self.btn_switch_mode=Button(
            rect=pygame.Rect(260, 372, 280, 36),
            text="Chưa có tài khoản? Đăng ký",
            font=self.theme.get_font(16),
           
            primary=False,
            bg_color=Colors.CARD_BG,
            fg_color=Colors.BTN_PRIMARY,
            border_color=Colors.CARD_BG,
            on_click=self._toggle_mode,
        )
    def on_enter(self,mode:str="login", **kwargs):
        self.mode=mode
        self.message=""
        self.input_username.value=""
        self.input_password.value=""
        self.input_pin.value=""
        self.input_username.focus=True
        self.input_password.focus=False
        self.input_pin.focus=False
        self._update_layout()
        pygame.key.start_text_input()
    def on_leave(self):
        pygame.key.stop_text_input()
    def _toggle_mode(self):
        self.mode="register" if self.mode=="login" else "login"
        self.message=""
        self._update_layout()
    def _update_layout(self):
        if self.mode=="login":
            self.card.rect=pygame.Rect(85, 30, 630, 420)
            self.input_username.rect= pygame.Rect(120, 140, 560, 52)
            self.input_password.rect= pygame.Rect(120, 226, 560, 52)
            self.btn_submit.rect= pygame.Rect(120, 310, 560, 50)
            self.btn_submit.text="Đăng nhập"
            self.btn_switch_mode.rect= pygame.Rect(260, 372, 280, 36)
            self.btn_switch_mode.text="Chưa có tài khoản? Đăng ký"
        else:
            self.card.rect = pygame.Rect(85, 15, 630, 450)
            self.input_username.rect = pygame.Rect(120, 110, 560, 48)
            self.input_password.rect = pygame.Rect(120, 186, 560, 48)
            self.input_pin.rect = pygame.Rect(120, 262, 560, 48)
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
            self.input_username.focused=True
            return
        if not password:
            self.message="Vui lòng nhập mật khẩu."
            self.input_password.focused=True
            return
        if self.mode =="register":
            if len(password)<6:
                self.message="Mật khẩu phải có ít nhất 6 ký tự."
                return
            if len(pin)<4:
                self.message="Mã PIN phải có ít nhất 4 ký tự."
                return
        self.app.settings["admin"] = {"user": username}
        self.app.persist_settings()
        self.message = "Thành công! Đang chuyển hướng..."
        self.app.switch_screen("face")
    def handle_event(self,event:pygame.event.Event)->bool:
        if self.input_username.handle_event(event):
            return True
        if self.input_password.handle_event(event):
            return True
        if self.mode == "register" and self.input_pin.handle_event(event):
            return True
        if self.btn_submit.handle_event(event):
            return True
        if self.btn_switch_mode.handle_event(event):
            return True
        if event.type==pygame.KEYDOWN and event.key == pygame.K_TAB:
            if self.mode=="login":
                self.input_username.focused,self.input_password.focused= self.input_password.focused,self.input_username.focused
            else:
                if self.input_username.focused:
                    self.input_username.focused=False
                    self.input_password.focused=True
                elif self.input_password.focused:
                    self.input_password.focused=False
                    self.input_pin.focused=True
                else:
                    self.input_pin.focused=False
                    self.input_username.focused=True
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
        title_str="Admin Login" if self.mode=="login" else "Tạo tài khoản quản trị"
        sub_str="Vui lòng đăng nhập để tiếp tục." if self.mode=="login" else "Vui lòng tạo tài khoản quản trị."
        ts_title=self.theme.get_font(24,bold=True).render(title_str,True,Colors.TEXT_DARK)
        ts_sub=self.theme.get_font(16).render(sub_str,True,Colors.TEXT_MUTED)
        surface.blit(ts_title,(mid-ts_title.get_width()//2,top+18))
        surface.blit(ts_sub,(mid-ts_sub.get_width()//2,top+48))
        
        surface.blit(self.theme.get_font(16).render("Tên đăng nhập",True,Colors.TEXT_DARK),(120,self.input_username.rect.y -20))
        self.input_username.draw(surface)
        surface.blit(self.theme.get_font(16).render("Mật khẩu",True,Colors.TEXT_DARK),(120,self.input_password.rect.y -20))
        self.input_password.draw(surface)
        if self.mode=="register":
            surface.blit(self.theme.get_font(16).render("Mã PIN",True,Colors.TEXT_DARK),(120,self.input_pin.rect.y -20))
            self.input_pin.draw(surface)
        self.btn_submit.draw(surface)
        self.btn_switch_mode.draw(surface)
        if self.message:
            msg_col=Colors.COLOR_DANGER if "vui lòng" in self.message.lower() or "phải" in self.message.lower() else Colors.GREEN_TEXT
            ts_msg=self.theme.get_font(16).render(self.message,True,msg_col)
            surface.blit(ts_msg,(mid - ts_msg.get_width()//2,self.btn_switch_mode.rect.bottom + 8))