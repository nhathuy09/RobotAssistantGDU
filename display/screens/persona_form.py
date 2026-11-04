
import json
import re
import pygame
from display.screens.persona_screen import PersonaScreen, PRESET_ROLES
from display.components.input_field import InputField
from display.components.button import Button
from display.theme import Colors
from database.repositories import PersonaRepository, SettingsRepository, HARDCODED_MOTION_RULES


class PersonaFormScreen(PersonaScreen):
    STYLES = ("Thân thiện", "Ngắn gọn", "Từng bước")

    def __init__(self, app_manager):
        self.form_ready = False
        self.advanced = False
        self.manual_prompt = False
        super().__init__(app_manager)
        self.form_fields = {}
        for key, y, hint, limit in (
            ('name', 112, 'Ví dụ: Đầu bếp', 36),
            ('task', 186, 'Gợi ý món ăn, hướng dẫn nấu ăn…', 500),
            ('extra', 340, 'Ví dụ: Ưu tiên món Việt, nguyên liệu dễ tìm', 500),
        ):
            self.form_fields[key] = InputField(
                rect=pygame.Rect(302, y, 472, 44), theme=self.theme,
                font=self.theme.get_font(15), placeholder=hint, max_length=limit)
        self.styles = {'Thân thiện'}
        self.style_buttons = []
        for i, label in enumerate(self.STYLES):
            self.style_buttons.append(Button(
                rect=pygame.Rect(302+i*160, 263, 152, 42), text=label,
                theme=self.theme, font=self.theme.get_font(14, bold=True),
                on_click=lambda label=label: self._toggle_style(label)))
        self.form_preview = Button(rect=pygame.Rect(486, 414, 124, 46), text='Xem trước', theme=self.theme,
                                   on_click=self._on_preview)
        self.form_save = Button(rect=pygame.Rect(622, 414, 152, 46), text='Lưu & Áp dụng', theme=self.theme,
                                on_click=self._on_apply)
        self.advanced_button = Button(rect=pygame.Rect(654, 14, 120, 40), text='Nâng cao', theme=self.theme,
                                      on_click=self._open_advanced)
        self.form_ready = True
        self._load_form()
        self._saved_draft = self._draft()

    def _load_from_settings(self):
        super()._load_from_settings()
        if self.form_ready:
            self._load_form()
            self._saved_draft = self._draft()

    def _load_form(self):
        records = PersonaRepository.get_all_personas()
        record = next((r for r in records if r['id'] == self.selected_role_id), {})
        try:
            data = json.loads(SettingsRepository.get('persona_form:'+self.selected_role_id, '{}'))
        except (ValueError, TypeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        self.form_fields['name'].value = data.get('name', record.get('name', ''))
        self.form_fields['task'].value = data.get('task', record.get('role_description', ''))
        self.form_fields['extra'].value = data.get('extra', '')
        self.styles = set(data.get('styles', ['Thân thiện']))
        self.manual_prompt = data.get('manual', bool(SettingsRepository.get('persona_prompt:'+self.selected_role_id)))
        self._last_form = self._form_values()
        self.input_custom_name.value = self.form_fields['name'].value

    def _form_values(self):
        return tuple(f.value for f in self.form_fields.values()) + (tuple(sorted(self.styles)),)

    def _draft(self):
        base = super()._draft()
        return base + (self._form_values(), self.manual_prompt) if self.form_ready else base

    def _toggle_style(self, label):
        if label in self.styles:
            self.styles.remove(label)
        else:
            self.styles.add(label)
        self._refresh_prompt()

    def _on_reset(self):
        super()._on_reset()
        if self.form_ready:
            self._load_form()

    def _refresh_prompt(self):
        if self.selected_role_id != 'custom':
            return
        values = self._form_values()
        if values == self._last_form:
            return
        self._last_form = values
        self.manual_prompt = False
        name = self.form_fields['name'].value.strip()
        task = self.form_fields['task'].value.strip()
        extra = self.form_fields['extra'].value.strip()
        style = ', '.join(s for s in self.STYLES if s in self.styles) or 'Tự nhiên, rõ ràng'
        self.input_custom_name.value = name
        self.custom_role_name = name
        self.prompt_text = (f'Bạn là Alexa, một trợ lý robot thông minh.\n'
                            f'- Vai trò hiện tại của bạn: {name}.\n'
                            f'- Trách nhiệm chính: {task}.\n'
                            f'- Phong cách trò chuyện: {style}.\n')
        if extra:
            self.prompt_text += f'- Yêu cầu thêm: {extra}\n'
        self.prompt_text += '\n'+HARDCODED_MOTION_RULES

    def _open_advanced(self):
        self._refresh_prompt()
        self.advanced = True
        self.manual_prompt = True
        self.keyboard.close()

    def _on_keyboard_submit(self):
        if self.form_ready and not self.advanced:
            self.keyboard.close()
            self._refresh_prompt()
        else:
            super()._on_keyboard_submit()

    def _on_keyboard_cancel(self):
        if self.form_ready and not self.advanced:
            self._on_keyboard_submit()
        else:
            super()._on_keyboard_cancel()

    def _on_preview(self):
        if self.form_ready and not self.advanced:
            self._refresh_prompt()
        super()._on_preview()

    def _on_apply(self):
        if not self.form_ready:
            return super()._on_apply()
        if not self.advanced:
            self._refresh_prompt()
        try:
            if self.selected_role_id == 'custom':
                name = self.form_fields['name'].value.strip()
                task = self.form_fields['task'].value.strip()
                if not name or (not task and not self.manual_prompt):
                    raise ValueError('Nhập tên vai trò và nhiệm vụ trước khi lưu.')
                self.input_custom_name.value = name
                self._sync_custom_role()
            else:
                name = self._get_current_role_title()
            data = {key: field.value for key, field in self.form_fields.items()}
            data.update(styles=sorted(self.styles), manual=self.manual_prompt)
            PersonaRepository.save_editor(self.selected_role_id, name, self.prompt_text, data)
            self._saved_draft = self._draft()
            self.save_error = False
            self.toast_message = 'Đã lưu. Áp dụng từ phiên trò chuyện tiếp theo.'
        except Exception as error:
            self.save_error = True
            self.toast_message = str(error) if isinstance(error, ValueError) else 'Lưu thất bại. Bản nháp được giữ lại.'
        self.toast_timer = pygame.time.get_ticks()

    def handle_event(self, event):
        if self.show_preview_modal:
            return super().handle_event(event)
        if self.advanced:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.back_btn_rect.collidepoint(event.pos):
                self.keyboard.close()
                self.advanced = False
                return True
            previous = self.selected_role_id
            handled = super().handle_event(event)
            if previous != self.selected_role_id:
                self._load_form()
                self.manual_prompt = True
            return handled
        if self.keyboard.visible:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self._on_keyboard_submit()
                return True
            if self.keyboard.handle_event(event):
                self._refresh_prompt()
                return True
            field = self.keyboard.active_input
            if field and field.handle_event(event):
                self._refresh_prompt()
                return True
            return True
        for button in (self.advanced_button, self.form_preview, self.form_save):
            if button.handle_event(event):
                return True
        if self.selected_role_id == 'custom':
            for button in self.style_buttons:
                if button.handle_event(event):
                    return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn_rect.collidepoint(event.pos):
                self.app_manager.switch_screen('face')
                return True
            for i, role in enumerate(PRESET_ROLES):
                if pygame.Rect(24, 82+i*62, 250, 54).collidepoint(event.pos):
                    self.selected_role_id = role['id']
                    self.prompt_text = PersonaRepository.get_system_instruction(role['id'])
                    self._load_form()
                    return True
            if self.selected_role_id == 'custom':
                for field in self.form_fields.values():
                    if field.rect.collidepoint(event.pos):
                        self.keyboard.open(field)
                        field.set_focus(True)
                        return True
        return False

    def update(self):
        if self.advanced:
            super().update()
        else:
            self.keyboard.update()
            for field in self.form_fields.values():
                field.update()
            self._refresh_prompt()
            if self.toast_message and pygame.time.get_ticks()-self.toast_timer > 4000:
                self.toast_message = ''

    def _text(self, surface, text, pos, size=14, bold=False, color=None):
        surface.blit(self.theme.get_font(size, bold=bold).render(text, True, color or self.TEXT_MAIN), pos)

    def draw(self, surface):
        if self.advanced:
            return super().draw(surface)
        surface.fill(self.PAGE_BG)
        self._text(surface, '‹ Quay lại', (24, 27), 15, True)
        self._text(surface, 'Vai trò của robot', (300, 24), 22, True)
        self.advanced_button.draw(surface)
        for i, role in enumerate(PRESET_ROLES):
            rect = pygame.Rect(24, 82+i*62, 250, 54)
            selected = role['id'] == self.selected_role_id
            pygame.draw.rect(surface, Colors.CARD_BG_MUTED, rect, border_radius=12)
            pygame.draw.rect(surface, self.ACCENT_GREEN if selected else self.CARD_BORDER, rect, 2 if selected else 1, border_radius=12)
            self._text(surface, 'Tùy chỉnh vai trò' if role['id']=='custom' else role['title'], (38, rect.y+18), 15, True)
        if self.selected_role_id == 'custom':
            for label, y in [('Tên vai trò', 88), ('Robot giúp việc gì?', 162), ('Phong cách trả lời', 239), ('Yêu cầu thêm (không bắt buộc)', 316)]:
                self._text(surface, label, (302, y), 14, True)
            for field in self.form_fields.values():
                field.draw(surface)
            for label, button in zip(self.STYLES, self.style_buttons):
                button.bg_color = Colors.PINE_GREEN if label in self.styles else Colors.CARD_BG
                button.fg_color = Colors.COLOR_WHITE if label in self.styles else self.TEXT_MAIN
                button.draw(surface)
        else:
            self._text(surface, self._get_current_role_title(), (302, 100), 19, True)
            lines = self._wrap_text(self.form_fields['task'].value, 456, self.theme.get_font(16))
            for i, line in enumerate(lines[:8]):
                self._text(surface, line, (302, 145+i*26), 16)
            self._text(surface, 'Chọn Tùy chỉnh vai trò để tạo vai trò riêng.', (302, 340), 14)
        note = 'Đang giữ prompt cũ. Sửa form sẽ tạo lại prompt.' if self.manual_prompt else 'Hướng dẫn được tạo tự động từ các trường trên'
        self._text(surface, note, (302, 388), 12, color=self.TEXT_MUTED)
        self._text(surface, 'Chưa lưu' if self.is_dirty() else 'Đã lưu', (24, 414), 14, True)
        self.form_preview.draw(surface)
        self.form_save.draw(surface)
        if self.toast_message:
            self._text(surface, self.toast_message, (24, 460), 12, color=Colors.ERROR_COLOR if self.save_error else self.ACCENT_GREEN)
        if self.show_preview_modal:
            original = self.prompt_text
            if not self.manual_prompt:
                self.prompt_text = '\n'.join([
                    'Vai trò: '+self.form_fields['name'].value,
                    'Nhiệm vụ: '+self.form_fields['task'].value,
                    'Phong cách: '+', '.join(sorted(self.styles)),
                    'Yêu cầu thêm: '+(self.form_fields['extra'].value or 'Không có'),
                ])
            self._draw_preview_modal(surface)
            self.prompt_text = original
        if self.keyboard.visible and not self.show_preview_modal:
            # Keep the active field above the keyboard without moving its hit box.
            pygame.draw.rect(surface, self.PAGE_BG, (282, 72, 518, 158))
            active = self.keyboard.active_input
            labels = {'name':'Tên vai trò', 'task':'Robot giúp việc gì?', 'extra':'Yêu cầu thêm'}
            key = next((k for k,v in self.form_fields.items() if v is active), 'name')
            self._text(surface, labels[key], (302, 82), 15, True)
            original_rect = active.rect
            active.rect = pygame.Rect(302, 116, 472, 44)
            active.draw(surface)
            active.rect = original_rect
            self._text(surface, 'Bấm Xong để trở về biểu mẫu.', (302, 178), 14)
            self.keyboard.draw(surface)
