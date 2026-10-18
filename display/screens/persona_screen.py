import pygame
from typing import Dict, List, Optional
from display.screens.base_screen import BaseScreen
from display.theme import Colors,Theme
from display.components.button import Button


ROLES = [
    {"id": "aiot", "title": "AIoT Ambassador", "sub": "Introduce smart technology.", "icon": "nodes"},
    {"id": "tech", "title": "Technical Expert", "sub": "Explain and troubleshoot.", "icon": "wrench"},
    {"id": "guide", "title": "University Guide", "sub": "Help visitors explore campus.", "icon": "cap"},
    {"id": "custom", "title": "Other / Custom Role", "sub": "Define your own personality.", "icon": "pencil"},
    {"id": "home", "title": "Smart Home Concierge", "sub": "Smart home concierge.", "icon": "pencil"},
]

DEFAULT_PROMPT = (
    "Friendly, patient, and practical. Explain smart home basics in simple terms, "
    "highlight privacy controls, and guide guests through setup and daily use. "
    "Use short sentences, avoid technical jargon, and invite questions before moving "
    "to the next step."
)

MAX_PROMPT = 300


class PersonaScreen(BaseScreen):
    """Màn hình cấu hình AI Persona & Vai trò tương tác của Robot."""

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.selected = "custom"
        self.prompts: Dict[str, str] = {role["id"]: DEFAULT_PROMPT for role in ROLES}
        self.prompt = DEFAULT_PROMPT
        self.cursor_pos = len(self.prompt)
        self.focus_prompt = False
        self.preview_visible = False
        self.status_message = ""

        # Layout
        self.back_btn_rect = pygame.Rect(18, 14, 44, 44)
        self.col_l_x = 18
        self.col_l_w = 364
        self.col_r_x = 400
        self.col_r_w = 382
        self.section_y = 78

        self.role_top = 104
        self.role_h = 52
        self.role_gap = 6
        self.role_rects: List[pygame.Rect] = []
        for i in range(len(ROLES)):
            y = self.role_top + i * (self.role_h + self.role_gap)
            self.role_rects.append(pygame.Rect(self.col_l_x, y, self.col_l_w, self.role_h))

        self.editor_rect = pygame.Rect(
            self.col_r_x,
            self.role_top,
            self.col_r_w,
            len(ROLES) * self.role_h + (len(ROLES) - 1) * self.role_gap,
        )
        self.textarea = pygame.Rect(
            self.editor_rect.x + 14,
            self.editor_rect.y + 46,
            self.editor_rect.w - 28,
            self.editor_rect.h - 80,
        )

        # Footer Buttons
        fy = 412
        fh = 42
        self.btn_save = Button(
            rect=pygame.Rect(800 - 18 - 146, fy, 146, fh),
            text="Apply & Save",
            theme=self.theme,
            font=self.theme.get_font(24),
            primary=True,
            on_click=self._on_save,
        )
        self.btn_preview = Button(
            rect=pygame.Rect(self.btn_save.rect.x - 10 - 130, fy, 130, fh),
            text="Preview",
            theme=self.theme,
            font=self.theme.get_font(24),
            primary=False,
            on_click=self._on_preview,
        )
        self.btn_reset = Button(
            rect=pygame.Rect(self.btn_preview.rect.x - 10 - 130, fy, 130, fh),
            text="Reset",
            theme=self.theme,
            font=self.theme.get_font(24),
            primary=False,
            on_click=self._on_reset,
        )

        self._restore_from_settings()

    def _restore_from_settings(self):
        saved = self.app_manager.settings.get("persona", {})
        if isinstance(saved, dict):
            sel = saved.get("selected")
            if sel in self.prompts:
                self.selected = sel
            p_dict = saved.get("prompts", {})
            if isinstance(p_dict, dict):
                for rid, p_val in p_dict.items():
                    if rid in self.prompts and isinstance(p_val, str):
                        self.prompts[rid] = p_val[:MAX_PROMPT]
        self.prompt = self.prompts[self.selected]
        self.cursor_pos = len(self.prompt)

    def on_enter(self, **kwargs):
        self._restore_from_settings()
        self.focus_prompt = False
        self.preview_visible = False
        pygame.key.start_text_input()

    def on_leave(self):
        self.focus_prompt = False
        self.preview_visible = False
        pygame.key.stop_text_input()

    def _on_save(self):
        self.prompts[self.selected] = self.prompt
        self.app_manager.settings["persona"] = {
            "selected": self.selected,
            "prompts": dict(self.prompts),
        }
        err = self.app_manager.persist_settings()
        self.status_message = err or "Đã lưu và áp dụng persona thành công."

    def _on_preview(self):
        self.preview_visible = True

    def _on_reset(self):
        self.prompt = DEFAULT_PROMPT
        self.prompts[self.selected] = DEFAULT_PROMPT
        self.cursor_pos = len(self.prompt)
        self.status_message = "Đã khôi phục prompt mặc định."

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.preview_visible:
            if event.type == pygame.MOUSEBUTTONDOWN or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self.preview_visible = False
                return True
            return True

        # Footer buttons
        if self.btn_save.handle_event(event):
            return True
        if self.btn_preview.handle_event(event):
            return True
        if self.btn_reset.handle_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn_rect.collidepoint(event.pos):
                self.app_manager.switch_screen("face")
                return True

            for idx, r in enumerate(self.role_rects):
                if r.collidepoint(event.pos):
                    self.prompts[self.selected] = self.prompt
                    self.selected = ROLES[idx]["id"]
                    self.prompt = self.prompts[self.selected]
                    self.cursor_pos = len(self.prompt)
                    self.focus_prompt = False
                    self.status_message = ""
                    return True

            if self.textarea.collidepoint(event.pos):
                self.focus_prompt = True
                self.cursor_pos = len(self.prompt)
                return True

            self.focus_prompt = False

        elif event.type == pygame.TEXTINPUT and self.focus_prompt:
            for ch in event.text:
                if ch.isprintable() and len(self.prompt) < MAX_PROMPT:
                    self.prompt = self.prompt[: self.cursor_pos] + ch + self.prompt[self.cursor_pos :]
                    self.cursor_pos += 1
            self.prompts[self.selected] = self.prompt
            return True

        elif event.type == pygame.KEYDOWN and self.focus_prompt:
            if event.key == pygame.K_BACKSPACE and self.cursor_pos > 0:
                self.prompt = self.prompt[: self.cursor_pos - 1] + self.prompt[self.cursor_pos :]
                self.cursor_pos -= 1
            elif event.key == pygame.K_DELETE and self.cursor_pos < len(self.prompt):
                self.prompt = self.prompt[: self.cursor_pos] + self.prompt[self.cursor_pos + 1 :]
            elif event.key == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.prompt), self.cursor_pos + 1)
            elif event.key == pygame.K_RETURN and len(self.prompt) < MAX_PROMPT:
                self.prompt = self.prompt[: self.cursor_pos] + "\n" + self.prompt[self.cursor_pos :]
                self.cursor_pos += 1
            elif event.key == pygame.K_ESCAPE:
                self.focus_prompt = False
            self.prompts[self.selected] = self.prompt
            return True

        return False

    def draw(self, surface: pygame.Surface):
        surface.fill(Colors.BG_PAGE)
        mouse_pos = pygame.mouse.get_pos()

        # Header
        hover_back = self.back_btn_rect.collidepoint(mouse_pos)
        pygame.draw.rect(surface, (248, 246, 240) if hover_back else Colors.CARD_BG, self.back_btn_rect, border_radius=14)
        pygame.draw.rect(surface, Colors.CARD_BORDER, self.back_btn_rect, 1, border_radius=14)
        # Mũi tên
        ax, ay = self.back_btn_rect.center
        pygame.draw.line(surface, Colors.TEXT_DARK, (ax + 5, ay), (ax - 5, ay), 2)
        pygame.draw.line(surface, Colors.TEXT_DARK, (ax - 5, ay), (ax, ay - 5), 2)
        pygame.draw.line(surface, Colors.TEXT_DARK, (ax - 5, ay), (ax, ay + 5), 2)

        title = self.theme.font_h1.render("AI Persona & Role Configuration", True, Colors.TEXT_DARK)
        surface.blit(title, (76, self.back_btn_rect.centery - title.get_height() // 2))

        # Cột trái: Vai trò
        surface.blit(self.theme.font_small_bold.render("ROBOT ROLE", True, Colors.TEXT_MUTED), (self.col_l_x, self.section_y))
        for idx, role in enumerate(ROLES):
            r = self.role_rects[idx]
            is_sel = (role["id"] == self.selected)
            hov = r.collidepoint(mouse_pos)

            bg = Colors.GREEN_BG if is_sel else ((250, 248, 244) if hov else Colors.CARD_BG)
            border = Colors.GREEN_CHECK if is_sel else Colors.CARD_BORDER
            pygame.draw.rect(surface, bg, r, border_radius=12)
            pygame.draw.rect(surface, border, r, 2 if is_sel else 1, border_radius=12)

            # Icon box
            ib = pygame.Rect(r.x + 10, r.centery - 16, 32, 32)
            pygame.draw.rect(surface, Colors.GREEN_BG if is_sel else (240, 240, 235), ib, border_radius=8)

            surface.blit(self.theme.font_body_bold.render(role["title"], True, Colors.TEXT_DARK), (ib.right + 10, r.y + 8))
            if role["sub"]:
                surface.blit(self.theme.font_small.render(role["sub"], True, Colors.TEXT_MUTED), (ib.right + 10, r.y + 28))

            # Radio check mark
            cx, cy = r.right - 24, r.centery
            if is_sel:
                pygame.draw.circle(surface, Colors.GREEN_CHECK, (cx, cy), 10)
                # checkmark
                pygame.draw.line(surface, getattr(Colors, "COLOR_WHITE", Colors.COLOR_TEETH), (cx - 4, cy), (cx - 1, cy + 3), 2)
                pygame.draw.line(surface, getattr(Colors, "COLOR_WHITE", Colors.COLOR_TEETH), (cx - 1, cy + 3), (cx + 4, cy - 3), 2)
            else:
                pygame.draw.circle(surface, Colors.BORDER_RADIO, (cx, cy), 10, 2)

        # Cột phải: Editor
        surface.blit(self.theme.font_small_bold.render("ACTIVE ROLE PROMPT", True, Colors.TEXT_MUTED), (self.col_r_x, self.section_y))
        er = self.editor_rect
        pygame.draw.rect(surface, Colors.CARD_BG, er, border_radius=14)
        pygame.draw.rect(surface, Colors.CARD_BORDER, er, 1, border_radius=14)

        surface.blit(self.theme.font_title.render("Tone, Behavior & System Rules", True, Colors.TEXT_DARK), (er.x + 14, er.y + 16))

        # Textarea
        ta = self.textarea
        border_col = Colors.BTN_PRIMARY if self.focus_prompt else Colors.CARD_BORDER
        pygame.draw.rect(surface, (244, 244, 240), ta, border_radius=10)
        pygame.draw.rect(surface, border_col, ta, 2 if self.focus_prompt else 1, border_radius=10)

        # Render wrapped text
        self._draw_wrapped_text(surface, self.prompt, ta.x + 10, ta.y + 10, ta.w - 20)

        # Character count
        cnt_str = f"{len(self.prompt)} / {MAX_PROMPT}"
        ts_cnt = self.theme.font_small.render(cnt_str, True, Colors.TEXT_MUTED)
        surface.blit(ts_cnt, (er.right - ts_cnt.get_width() - 14, er.bottom - 22))

        # Footer divider & Buttons
        pygame.draw.line(surface, Colors.CARD_BORDER, (0, 400), (800, 400), 1)

        msg = self.status_message or "Role prompt  •  persona applied"
        surface.blit(self.theme.font_small.render(msg, True, Colors.TEXT_MUTED), (18, 424))

        self.btn_reset.draw(surface)
        self.btn_preview.draw(surface)
        self.btn_save.draw(surface)

        if self.preview_visible:
            self._draw_preview_modal(surface)

    def _draw_wrapped_text(self, surface: pygame.Surface, text: str, x: int, y: int, max_w: int):
        cur_y = y
        line_h = self.theme.font_body.get_height() + 4
        for paragraph in text.split("\n"):
            words = paragraph.split(" ")
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if self.theme.font_body.size(test)[0] <= max_w:
                    line = test
                else:
                    if line:
                        surface.blit(self.theme.font_body.render(line, True, Colors.TEXT_DARK), (x, cur_y))
                        cur_y += line_h
                    line = w
            if line:
                surface.blit(self.theme.font_body.render(line, True, Colors.TEXT_DARK), (x, cur_y))
            cur_y += line_h

    def _draw_preview_modal(self, surface: pygame.Surface):
        shade = pygame.Surface((800, 480), pygame.SRCALPHA)
        shade.fill((43, 48, 58, 120))
        surface.blit(shade, (0, 0))

        panel = pygame.Rect(92, 50, 616, 380)
        pygame.draw.rect(surface, Colors.BG_PAGE, panel, border_radius=16)
        pygame.draw.rect(surface, Colors.CARD_BORDER, panel, 1, border_radius=16)

        surface.blit(self.theme.font_title.render("Prompt Preview", True, Colors.TEXT_DARK), (panel.x + 20, panel.y + 24))
        surface.blit(self.theme.font_small.render("Chạm bất kỳ đâu hoặc bấm Esc để đóng", True, Colors.TEXT_MUTED), (panel.right - 240, panel.y + 26))

        content_rect = pygame.Rect(panel.x + 20, panel.y + 56, panel.w - 40, panel.h - 76)
        self._draw_wrapped_text(surface, self.prompt, content_rect.x, content_rect.y, content_rect.w)
