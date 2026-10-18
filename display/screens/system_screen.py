import pygame
from typing import Dict, List

from display.screens.base_screen import BaseScreen
from display.theme import Colors
from display.components.button import Button


PRESETS = [
    {
        "id": "gdu",
        "title": "GDU Ambassador Template",
        "sub": "Welcome and guide visitors",
        "prompt": (
            "**Persona rules**\n"
            "You are a helpful GDU ambassador. Be welcoming, accurate and respectful. "
            "Greet visitors warmly and offer assistance before they ask.\n\n"
            "**Communication guidelines**\n"
            "Use clear, concise language. Ask a question when the request is unclear. "
            "Keep responses short and actionable.\n\n"
            "**Knowledge-base context**\n"
            "Use only approved knowledge-base context. Never invent institutional facts. "
            "If unsure, offer to look it up."
        ),
    },
    {
        "id": "tech",
        "title": "Tech Expert Template",
        "sub": "Explain and troubleshoot",
        "prompt": (
            "**Persona rules**\n"
            "You are a technical expert. Be precise, methodical and patient with users.\n\n"
            "**Communication guidelines**\n"
            "Use step-by-step instructions. Confirm understanding before moving on. "
            "Explain the why, not just the how.\n\n"
            "**Knowledge-base context**\n"
            "Reference official documentation. If the issue is outside your scope, "
            "escalate to a human technician."
        ),
    },
    {
        "id": "custom",
        "title": "Custom Manual",
        "sub": "Write your own instructions",
        "prompt": (
            "**Persona rules**\n"
            "Describe the robot's personality, tone and values here.\n\n"
            "**Communication guidelines**\n"
            "Define how the robot should talk, when to ask questions, and what to avoid.\n\n"
            "**Knowledge-base context**\n"
            "List which sources the robot may cite and how to handle uncertainty."
        ),
    },
]

MAX_PROMPT = 2000


class SystemScreen(BaseScreen):
    """Màn hình biên soạn System Instruction nâng cao của BD-1."""

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.selected = "gdu"
        self.prompts: Dict[str, str] = {
            preset["id"]: preset["prompt"] for preset in PRESETS
        }
        self.prompt = self.prompts[self.selected]
        self.cursor_pos = len(self.prompt)
        self.scroll_y = 0
        self.focus_prompt = False
        self.preview_visible = False
        self.status_message = ""

        # Layout
        self.back_btn_rect = pygame.Rect(22, 16, 44, 44)
        self.col_l_x = 22
        self.col_l_w = 290
        self.col_r_x = 330
        self.col_r_w = 448

        self.card_rects: List[pygame.Rect] = []
        for i in range(len(PRESETS)):
            y = 110 + i * (68 + 10)
            self.card_rects.append(
                pygame.Rect(self.col_l_x, y, self.col_l_w, 68)
            )

        self.textarea = pygame.Rect(self.col_r_x, 110, self.col_r_w, 280)

        # Footer buttons
        footer_y = 414
        footer_h = 44
        self.btn_save = Button(
            rect=pygame.Rect(800 - 22 - 160, footer_y, 160, footer_h),
            text="Apply & Save",
            theme=self.theme,
            font=self.theme.get_font(24, bold=True),
            primary=True,
            on_click=self._on_save,
        )
        self.btn_preview = Button(
            rect=pygame.Rect(
                self.btn_save.rect.x - 10 - 120, footer_y, 120, footer_h
            ),
            text="Preview",
            theme=self.theme,
            font=self.theme.get_font(24, bold=True),
            primary=False,
            on_click=self._on_preview,
        )
        self.btn_reset = Button(
            rect=pygame.Rect(22, footer_y, 160, footer_h),
            text="Reset to Default",
            theme=self.theme,
            font=self.theme.get_font(24, bold=True),
            primary=False,
            on_click=self._on_reset,
        )

        self._restore_from_settings()

    def _restore_from_settings(self):
        """Khôi phục cấu hình đã lưu, nếu có."""
        settings = getattr(self.app_manager, "settings", {})
        if not isinstance(settings, dict):
            settings = {}

        saved = settings.get("instruction", {})
        if isinstance(saved, dict):
            selected = saved.get("selected")
            if selected in self.prompts:
                self.selected = selected

            saved_prompts = saved.get("prompts", {})
            if isinstance(saved_prompts, dict):
                for preset_id, value in saved_prompts.items():
                    if preset_id in self.prompts and isinstance(value, str):
                        self.prompts[preset_id] = value[:MAX_PROMPT]

        self.prompt = self.prompts[self.selected]
        self.cursor_pos = len(self.prompt)
        self.scroll_y = 0

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

        settings = getattr(self.app_manager, "settings", None)
        if not isinstance(settings, dict):
            self.status_message = "Không tìm thấy cấu hình settings để lưu."
            return

        settings["instruction"] = {
            "selected": self.selected,
            "prompts": dict(self.prompts),
        }

        persist = getattr(self.app_manager, "persist_settings", None)
        if callable(persist):
            try:
                result = persist()
                self.status_message = (
                    result if isinstance(result, str) and result
                    else "Đã lưu system instruction thành công."
                )
            except Exception as exc:
                self.status_message = f"Lỗi khi lưu cấu hình: {exc}"
        else:
            self.status_message = (
                "Đã cập nhật instruction trong bộ nhớ; "
                "app_manager chưa có persist_settings()."
            )

    def _on_preview(self):
        self.prompts[self.selected] = self.prompt
        self.preview_visible = True

    def _on_reset(self):
        default_prompt = next(
            preset["prompt"] for preset in PRESETS
            if preset["id"] == self.selected
        )
        self.prompt = default_prompt
        self.prompts[self.selected] = default_prompt
        self.cursor_pos = len(self.prompt)
        self.scroll_y = 0
        self.status_message = "Đã khôi phục instruction mặc định."

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.preview_visible:
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                or (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_ESCAPE
                )
            ):
                self.preview_visible = False
                return True
            return True

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

            for idx, rect in enumerate(self.card_rects):
                if rect.collidepoint(event.pos):
                    self.prompts[self.selected] = self.prompt
                    self.selected = PRESETS[idx]["id"]
                    self.prompt = self.prompts[self.selected]
                    self.cursor_pos = len(self.prompt)
                    self.scroll_y = 0
                    self.focus_prompt = False
                    self.status_message = ""
                    return True

            if self.textarea.collidepoint(event.pos):
                self.focus_prompt = True
                self.cursor_pos = len(self.prompt)
                return True

            self.focus_prompt = False

        elif event.type == pygame.MOUSEWHEEL:
            if self.textarea.collidepoint(pygame.mouse.get_pos()):
                self.scroll_y = max(0, self.scroll_y - event.y * 30)
                return True

        elif event.type == pygame.TEXTINPUT and self.focus_prompt:
            new_text = event.text
            if len(self.prompt) + len(new_text) <= MAX_PROMPT:
                self.prompt = (
                    self.prompt[:self.cursor_pos]
                    + new_text
                    + self.prompt[self.cursor_pos:]
                )
                self.cursor_pos += len(new_text)
                self.prompts[self.selected] = self.prompt
            return True

        elif event.type == pygame.KEYDOWN and self.focus_prompt:
            if event.key == pygame.K_BACKSPACE and self.cursor_pos > 0:
                self.prompt = (
                    self.prompt[:self.cursor_pos - 1]
                    + self.prompt[self.cursor_pos:]
                )
                self.cursor_pos -= 1
            elif event.key == pygame.K_DELETE and self.cursor_pos < len(self.prompt):
                self.prompt = (
                    self.prompt[:self.cursor_pos]
                    + self.prompt[self.cursor_pos + 1:]
                )
            elif event.key == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.prompt), self.cursor_pos + 1)
            elif event.key == pygame.K_RETURN and len(self.prompt) < MAX_PROMPT:
                self.prompt = (
                    self.prompt[:self.cursor_pos]
                    + "\n"
                    + self.prompt[self.cursor_pos:]
                )
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
        back_bg = (248, 246, 240) if hover_back else Colors.CARD_BG
        pygame.draw.rect(
            surface, back_bg, self.back_btn_rect, border_radius=12
        )
        pygame.draw.rect(
            surface, Colors.CARD_BORDER, self.back_btn_rect, 1,
            border_radius=12
        )
        ax, ay = self.back_btn_rect.center
        pygame.draw.line(surface, Colors.TEXT_DARK, (ax + 5, ay), (ax - 5, ay), 2)
        pygame.draw.line(surface, Colors.TEXT_DARK, (ax - 5, ay), (ax, ay - 5), 2)
        pygame.draw.line(surface, Colors.TEXT_DARK, (ax - 5, ay), (ax, ay + 5), 2)

        title = self.theme.font_h1.render(
            "Advanced System Instruction Editor", True, Colors.TEXT_DARK
        )
        surface.blit(
            title,
            (78, self.back_btn_rect.centery - title.get_height() // 2)
        )

        # Left column: presets
        surface.blit(
            self.theme.font_title.render("Role Presets", True, Colors.TEXT_DARK),
            (self.col_l_x, 82),
        )
        for idx, preset in enumerate(PRESETS):
            rect = self.card_rects[idx]
            is_selected = preset["id"] == self.selected
            is_hovered = rect.collidepoint(mouse_pos)

            if is_selected:
                bg = (235, 240, 243)
            elif is_hovered:
                bg = (250, 248, 244)
            else:
                bg = Colors.CARD_BG

            border = Colors.BTN_PRIMARY if is_selected else Colors.CARD_BORDER
            pygame.draw.rect(surface, bg, rect, border_radius=12)
            pygame.draw.rect(
                surface, border, rect, 2 if is_selected else 1,
                border_radius=12
            )

            surface.blit(
                self.theme.font_body_bold.render(
                    preset["title"], True, Colors.TEXT_DARK
                ),
                (rect.x + 14, rect.y + 12),
            )
            surface.blit(
                self.theme.font_small.render(
                    preset["sub"], True, Colors.TEXT_MUTED
                ),
                (rect.x + 14, rect.y + 36),
            )

            cx, cy = rect.right - 24, rect.centery
            if is_selected:
                pygame.draw.circle(surface, Colors.BTN_PRIMARY, (cx, cy), 10)
                check_color = getattr(Colors, "COLOR_WHITE", Colors.COLOR_TEETH)
                pygame.draw.line(surface, check_color, (cx - 4, cy), (cx - 1, cy + 3), 2)
                pygame.draw.line(surface, check_color, (cx - 1, cy + 3), (cx + 4, cy - 3), 2)
            else:
                pygame.draw.circle(
                    surface, Colors.BORDER_RADIO, (cx, cy), 10, 2
                )

        # Right column: editor
        surface.blit(
            self.theme.font_title.render(
                "System instruction", True, Colors.TEXT_DARK
            ),
            (self.col_r_x, 82),
        )
        hint = self.status_message or (
            "Đang chỉnh sửa..." if self.focus_prompt else "Chạm để chỉnh sửa"
        )
        hint_surface = self.theme.font_small.render(
            hint, True, Colors.TEXT_MUTED
        )
        surface.blit(
            hint_surface,
            (self.col_r_x + self.col_r_w - hint_surface.get_width(), 84),
        )

        textarea = self.textarea
        border_color = Colors.BTN_PRIMARY if self.focus_prompt else Colors.CARD_BORDER
        pygame.draw.rect(surface, Colors.CARD_BG, textarea, border_radius=12)
        pygame.draw.rect(
            surface, border_color, textarea,
            2 if self.focus_prompt else 1, border_radius=12
        )

        old_clip = surface.get_clip()
        inner_rect = textarea.inflate(-20, -20)
        surface.set_clip(inner_rect)
        self._draw_scrollable_text(surface, inner_rect)
        surface.set_clip(old_clip)

        count_surface = self.theme.font_small.render(
            f"{len(self.prompt)} / {MAX_PROMPT} ký tự", True, Colors.TEXT_MUTED
        )
        surface.blit(
            count_surface,
            (textarea.right - count_surface.get_width() - 14, textarea.bottom - 20),
        )

        # Footer
        pygame.draw.line(surface, Colors.CARD_BORDER, (0, 400), (800, 400), 1)
        self.btn_reset.draw(surface)
        self.btn_preview.draw(surface)
        self.btn_save.draw(surface)

        if self.preview_visible:
            self._draw_preview_modal(surface)

    def _draw_scrollable_text(self, surface: pygame.Surface, inner_rect: pygame.Rect):
        y = inner_rect.y - self.scroll_y
        line_height = self.theme.font_body.get_height() + 4

        for paragraph in self.prompt.split("\n"):
            is_header = paragraph.startswith("**") and paragraph.endswith("**")
            text = paragraph[2:-2] if is_header else paragraph
            font = self.theme.font_body_bold if is_header else self.theme.font_body

            words = paragraph.split(" ") if not is_header else text.split(" ")
            line = ""
            for word in words:
                candidate = (line + " " + word).strip()
                if font.size(candidate)[0] <= inner_rect.w:
                    line = candidate
                else:
                    if line and inner_rect.y - line_height <= y <= inner_rect.bottom:
                        surface.blit(font.render(line, True, Colors.TEXT_DARK), (inner_rect.x, y))
                    y += line_height
                    line = word

            if line and inner_rect.y - line_height <= y <= inner_rect.bottom:
                surface.blit(font.render(line, True, Colors.TEXT_DARK), (inner_rect.x, y))
            y += line_height + 4

    def _draw_preview_modal(self, surface: pygame.Surface):
        shade = pygame.Surface((800, 480), pygame.SRCALPHA)
        shade.fill((43, 48, 58, 120))
        surface.blit(shade, (0, 0))

        panel = pygame.Rect(70, 42, 660, 396)
        pygame.draw.rect(surface, Colors.BG_PAGE, panel, border_radius=16)
        pygame.draw.rect(surface, Colors.CARD_BORDER, panel, 1, border_radius=16)

        surface.blit(
            self.theme.font_title.render(
                f"Preview: {self.selected.upper()}", True, Colors.TEXT_DARK
            ),
            (panel.x + 20, panel.y + 20),
        )
        surface.blit(
            self.theme.font_small.render(
                "Chạm hoặc nhấn Esc để đóng", True, Colors.TEXT_MUTED
            ),
            (panel.right - 200, panel.y + 22),
        )

        inner = panel.inflate(-40, -70)
        inner.y += 15
        pygame.draw.rect(surface, Colors.CARD_BG, inner, border_radius=10)
        pygame.draw.rect(surface, Colors.CARD_BORDER, inner, 1, border_radius=10)

        old_clip = surface.get_clip()
        surface.set_clip(inner.inflate(-16, -16))
        self._draw_scrollable_text(surface, inner.inflate(-16, -16))
        surface.set_clip(old_clip)
