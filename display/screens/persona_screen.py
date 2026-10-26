import math
from typing import Dict, List, Optional
import pygame

from display.components.button import Button
from display.components.input_field import InputField
from display.components.virtual_keyboard import VirtualKeyboard
from display.screens.base_screen import BaseScreen
from display.theme import Colors, Theme
from database.repositories import PersonaRepository, SystemLogRepository

# Danh sách các vai trò mẫu đồng bộ với Database SQLite
PRESET_ROLES = [
    {
        "id": "guide_gdu",
        "title": "Hướng dẫn viên GDU",
        "desc": "Chào đón sinh viên & khách tham quan GDU",
    },
    {
        "id": "aiot",
        "title": "Đại sứ AIoT",
        "desc": "Giới thiệu sản phẩm ấm áp, truyền cảm hứng",
    },
    {
        "id": "tech",
        "title": "Chuyên gia Kỹ thuật",
        "desc": "Khắc phục sự cố phần cứng & code chuẩn xác",
    },
    {
        "id": "receptionist",
        "title": "Lễ tân BD-1",
        "desc": "Chào đón & điều phối thông tin khách hàng",
    },
    {
        "id": "custom",
        "title": "Vai trò Tùy chỉnh",
        "desc": "Tự định hình bản sắc riêng cho Robot",
    },
]

MAX_PROMPT = 2000


class PromptKeyboardAdapter:
    """Adapter cho phép bàn phím ảo thao tác trực tiếp trên chuỗi Prompt."""

    def __init__(self, screen: "PersonaScreen"):
        self.screen = screen
        self.max_length = MAX_PROMPT
        self.is_numeric = False
        self.on_submit = None
        self.on_text_change = None

    @property
    def value(self) -> str:
        return self.screen.prompt_text

    @value.setter
    def value(self, val: str):
        self.screen.prompt_text = val[:MAX_PROMPT]
        self.screen._ensure_cursor_visible()

    def set_focus(self, focused: bool):
        self.screen.is_editing_prompt = focused


class PersonaScreen(BaseScreen):
    """Màn hình cấu hình Vai trò & Tính cách chuẩn BD-1 Forest Green hoàn thiện."""

    PAGE_BG = Colors.PAGE_BG
    CARD_BG = Colors.CARD_BG_MUTED
    CARD_BORDER = Colors.CARD_BORDER
    TEXT_MAIN = Colors.TEXT_MAIN
    TEXT_MUTED = Colors.TEXT_MUTED
    SAGE_MUTED = Colors.SAGE_MUTED
    ACCENT_GREEN = Colors.PINE_GREEN
    SUCCESS_COLOR = Colors.SUCCESS_COLOR

    def __init__(self, app_manager):
        super().__init__(app_manager)
        self.selected_role_id = "guide_gdu"
        self.custom_role_name = "Vai trò Tùy chỉnh"
        self.prompt_text = ""

        # Trạng thái thông báo Toast
        self.toast_message = ""
        self.toast_timer = 0

        # Trạng thái cửa sổ xem trước (Preview Modal)
        self.show_preview_modal = False
        self.preview_scroll_y = 0

        # Chế độ soạn thảo văn bản & Cuộn dòng
        self.is_editing_prompt = False
        self.cursor_visible = True
        self.last_cursor_toggle = 0
        self.prompt_scroll_line = 0
        self.max_scroll_line = 0

        # Tọa độ Layout
        self.back_btn_rect = pygame.Rect(24, 16, 110, 36)

        # Cột trái: PRESET ROLES (5 vai trò)
        self.col_left_rect = pygame.Rect(24, 74, 276, 392)
        self.role_rects: List[pygame.Rect] = []
        card_h = 50
        card_gap = 5
        for i in range(len(PRESET_ROLES)):
            ry = 80 + i * (card_h + card_gap)
            self.role_rects.append(pygame.Rect(24, ry, 276, card_h))

        # Thanh input Tên vai trò tùy chỉnh ở dưới cột trái
        self.input_custom_rect = pygame.Rect(24, 404, 276, 38)
        self.input_custom_name = InputField(
            rect=self.input_custom_rect,
            placeholder="Tên vai trò...",
            theme=self.theme,
            font=self.theme.get_font(14),
            text=self.custom_role_name,
            max_length=36,
        )
        self.input_custom_name.bg_color = Colors.CARD_BG
        self.input_custom_name.border_color = Colors.MIST_GRAY
        self.input_custom_name.focus_color = Colors.PINE_GREEN
        self.input_custom_name.border_radius = 12

        # Cột phải: Khung chi tiết
        self.editor_card_rect = pygame.Rect(316, 74, 460, 392)
        self.textarea_rect = pygame.Rect(332, 142, 428, 220)
        self.btn_scroll_up_rect = pygame.Rect(self.textarea_rect.right - 26, self.textarea_rect.y + 6, 20, 20)
        self.btn_scroll_down_rect = pygame.Rect(self.textarea_rect.right - 26, self.textarea_rect.bottom - 26, 20, 20)

        # Nút bật bàn phím ảo cho prompt
        self.btn_open_keyboard_rect = pygame.Rect(self.editor_card_rect.right - 100, self.editor_card_rect.y + 14, 84, 26)

        # Hàng nút bấm
        btn_y = 398
        card_r = self.editor_card_rect.right - 16

        self.btn_apply = Button(
            rect=pygame.Rect(card_r - 138, btn_y, 138, 42),
            text="Lưu & Áp dụng",
            theme=self.theme,
            font=self.theme.get_font(13, bold=True),
            bg_color=Colors.PINE_GREEN,
            fg_color=Colors.COLOR_WHITE,
            border_color=Colors.PINE_GREEN,
            border_radius=12,
            primary=True,
            on_click=self._on_apply,
        )

        self.btn_preview = Button(
            rect=pygame.Rect(self.btn_apply.rect.left - 10 - 96, btn_y, 96, 42),
            text="Xem trước",
            theme=self.theme,
            font=self.theme.get_font(13, bold=True),
            bg_color=Colors.CARD_BG,
            fg_color=Colors.FOREST_GREEN,
            border_color=Colors.MIST_GRAY,
            border_radius=12,
            primary=False,
            on_click=self._on_preview,
        )

        self.btn_reset = Button(
            rect=pygame.Rect(self.btn_preview.rect.left - 10 - 80, btn_y, 80, 42),
            text="Đặt lại",
            theme=self.theme,
            font=self.theme.get_font(13, bold=True),
            bg_color=Colors.CARD_BG,
            fg_color=Colors.FOREST_GREEN,
            border_color=Colors.MIST_GRAY,
            border_radius=12,
            primary=False,
            on_click=self._on_reset,
        )

        # Nút đóng trong Modal Preview
        self.modal_rect = pygame.Rect(110, 45, 580, 390)
        self.modal_close_rect = pygame.Rect(self.modal_rect.right - 44, self.modal_rect.y + 14, 30, 30)
        self.modal_prompt_box = pygame.Rect(self.modal_rect.x + 24, self.modal_rect.y + 140, self.modal_rect.width - 48, 175)
        self.modal_btn_close = Button(
            rect=pygame.Rect(self.modal_rect.right - 190, self.modal_rect.bottom - 54, 80, 38),
            text="Đóng",
            theme=self.theme,
            font=self.theme.get_font(13, bold=True),
            bg_color=self.CARD_BORDER,
            fg_color=self.TEXT_MAIN,
            border_color=self.CARD_BORDER,
            border_radius=10,
            primary=False,
            on_click=self._close_preview,
        )
        self.modal_btn_apply = Button(
            rect=pygame.Rect(self.modal_rect.right - 102, self.modal_rect.bottom - 54, 88, 38),
            text="Áp dụng",
            theme=self.theme,
            font=self.theme.get_font(13, bold=True),
            bg_color=self.ACCENT_GREEN,
            fg_color=Colors.COLOR_WHITE,
            border_color=self.ACCENT_GREEN,
            border_radius=10,
            primary=True,
            on_click=self._apply_from_modal,
        )

        # Bàn phím ảo cảm ứng
        self.keyboard = VirtualKeyboard(
            top_y=230,
            height=250,
            width=800,
            on_submit=self._on_keyboard_submit,
            on_cancel=self._on_keyboard_cancel,
        )
        self.prompt_adapter = PromptKeyboardAdapter(self)

        self._load_from_settings()

    def on_enter(self, **kwargs):
        """Khởi tạo trạng thái mới khi chuyển vào màn hình Persona."""
        self._load_from_settings()
        self.show_preview_modal = False
        self.keyboard.close()
        self.toast_message = ""
        self.is_editing_prompt = False
        self.prompt_scroll_line = 0

    def _load_from_settings(self):
        try:
            active = PersonaRepository.get_active_persona()
            if active:
                self.selected_role_id = active["id"]
                if active["id"] == "custom":
                    self.custom_role_name = active["name"]
                    self.input_custom_name.value = self.custom_role_name
            self.prompt_text = PersonaRepository.get_system_instruction()
        except Exception as e:
            print(f"[PERSONA LOAD ERROR] {e}")

    def _get_current_role_title(self) -> str:
        if self.selected_role_id == "custom":
            return self.custom_role_name.strip() or "Vai trò Tùy chỉnh"
        role_obj = next((r for r in PRESET_ROLES if r["id"] == self.selected_role_id), None)
        return role_obj["title"] if role_obj else "Vai trò"

    def _on_reset(self):
        """Khôi phục nội dung vai trò về Hướng dẫn viên GDU mặc định ban đầu."""
        try:
            PersonaRepository.set_active_persona("guide_gdu")
            self.selected_role_id = "guide_gdu"
            self.prompt_text = PersonaRepository.get_system_instruction()
            self.prompt_scroll_line = 0
            self.toast_message = "Đã đặt lại vai trò về Hướng dẫn viên GDU!"
            self.toast_timer = pygame.time.get_ticks()
            SystemLogRepository.log("INFO", "PERSONA", "Đã đặt lại vai trò về Hướng dẫn viên GDU mặc định.")
        except Exception as e:
            self.toast_message = f"Lỗi: {e}"
            self.toast_timer = pygame.time.get_ticks()

    def _on_preview(self):
        """Mở cửa sổ xem trước (Preview Modal)."""
        self.show_preview_modal = True
        self.preview_scroll_y = 0
        if self.keyboard.visible:
            self.keyboard.close()

    def _close_preview(self):
        self.show_preview_modal = False

    def _apply_from_modal(self):
        self.show_preview_modal = False
        self._on_apply()

    def _on_apply(self):
        """Lưu và áp dụng cấu hình vai trò vào hệ thống database."""
        try:
            if self.selected_role_id == "custom":
                self.custom_role_name = self.input_custom_name.value.strip() or "Vai trò Tùy chỉnh"
                PersonaRepository.save_persona(
                    persona_id="custom",
                    name=self.custom_role_name,
                    role_description="Trợ lý Robot thông minh hỗ trợ đa năng theo yêu cầu",
                    tone_style="Nhiệt tình, chu đáo, phản hồi tự nhiên và chính xác",
                    include_gdu_knowledge=0,
                    is_active=1
                )
            else:
                PersonaRepository.set_active_persona(self.selected_role_id)

            self.prompt_text = PersonaRepository.get_system_instruction()

            # Đồng bộ ngược vào settings dict của app_manager để tương thích
            self.app_manager.settings["persona"] = {
                "selected_role": self.selected_role_id,
                "custom_role_name": self.custom_role_name,
            }
            self.app_manager.persist_settings()

            SystemLogRepository.log("OK", "PERSONA", f"Đã áp dụng vai trò '{self._get_current_role_title()}' vào DB.")

            if hasattr(self.app_manager, "set_face_state"):
                try:
                    self.app_manager.set_face_state("HAPPY")
                except Exception:
                    pass
            self.toast_message = "Đã lưu và áp dụng vai trò thành công!"
            self.toast_timer = pygame.time.get_ticks()
        except Exception as e:
            self.toast_message = f"Lỗi lưu vai trò: {e}"
            self.toast_timer = pygame.time.get_ticks()

    def _on_keyboard_submit(self):
        if self.keyboard.active_input is self.input_custom_name:
            self.custom_role_name = self.input_custom_name.value.strip() or "Vai trò Tùy chỉnh"
        elif self.keyboard.active_input is self.prompt_adapter:
            self.is_editing_prompt = False
        self.keyboard.close()

    def _on_keyboard_cancel(self):
        self.is_editing_prompt = False
        self.keyboard.close()

    def _get_wrapped_lines(self) -> List[str]:
        """Bộ nhớ đệm (cache) phân tách dòng cho prompt, chỉ tính lại khi văn bản thay đổi."""
        font = self.theme.get_font(13)
        max_w = self.textarea_rect.width - 36
        key = (self.prompt_text, max_w)
        if getattr(self, "_cached_wrap_key", None) == key:
            return self._cached_wrap_lines
        self._cached_wrap_lines = self._wrap_text(self.prompt_text, max_w, font)
        self._cached_wrap_key = key
        return self._cached_wrap_lines

    def _ensure_cursor_visible(self):
        """Đảm bảo cuộn tới dòng đang có con trỏ khi gõ."""
        lines = self._get_wrapped_lines()
        visible_lines = max(1, (self.textarea_rect.height - 24) // 20)
        if len(lines) > visible_lines:
            self.prompt_scroll_line = max(0, len(lines) - visible_lines)

    @staticmethod
    def _wrap_text(text: str, max_w: int, font: pygame.font.Font) -> List[str]:
        paragraphs = text.split("\n")
        lines = []
        for p in paragraphs:
            if not p:
                lines.append("")
                continue
            words = p.split(" ")
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if font.size(test)[0] <= max_w:
                    cur = test
                else:
                    lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
        return lines

    def _calc_max_scroll(self) -> int:
        """Tính số dòng cuộn tối đa dựa trên độ dài văn bản prompt."""
        visible_lines = max(1, (self.textarea_rect.height - 24) // 20)
        lines = self._get_wrapped_lines()
        return max(0, len(lines) - visible_lines)

    def handle_event(self, event: pygame.event.Event) -> bool:
        # 1. Nếu cửa sổ xem trước (Preview Modal) đang mở
        if self.show_preview_modal:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._close_preview()
                return True
            if event.type == pygame.MOUSEWHEEL:
                self.preview_scroll_y = max(0, self.preview_scroll_y - event.y * 24)
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.modal_close_rect.collidepoint(event.pos):
                    self._close_preview()
                    return True
                if not self.modal_rect.collidepoint(event.pos):
                    self._close_preview()
                    return True
            if self.modal_btn_close.handle_event(event):
                return True
            if self.modal_btn_apply.handle_event(event):
                return True
            return True

        # 2. Xử lý bàn phím ảo nếu đang hiển thị
        if self.keyboard.visible:
            # Nhấp vào nút "Xuống dòng" hoặc "Xong" nhanh trên banner soạn thảo prompt
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                banner_bar_y = self.keyboard.rect.y - 46
                btn_clear_rect = pygame.Rect(780 - 176, banner_bar_y + 4, 80, 34)
                btn_done_rect = pygame.Rect(780 - 88, banner_bar_y + 4, 80, 34)
                btn_nl_rect = pygame.Rect(780 - 180, banner_bar_y + 4, 86, 34)

                if self.keyboard.active_input is self.input_custom_name:
                    if btn_clear_rect.collidepoint(event.pos):
                        self.input_custom_name.value = ""
                        return True
                    elif btn_done_rect.collidepoint(event.pos):
                        self._on_keyboard_submit()
                        return True

                elif self.keyboard.active_input is self.prompt_adapter:
                    if btn_nl_rect.collidepoint(event.pos):
                        if len(self.prompt_text) < MAX_PROMPT:
                            self.prompt_text += "\n"
                            self._ensure_cursor_visible()
                        return True
                    elif btn_done_rect.collidepoint(event.pos):
                        self._on_keyboard_submit()
                        return True

            if self.keyboard.handle_event(event):
                if self.keyboard.active_input is self.input_custom_name:
                    self.custom_role_name = self.input_custom_name.value
                return True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Nếu chạm vào vùng trên bàn phím ảo mà không phải ô đang gõ
                if event.pos[1] < self.keyboard.rect.y - 48:
                    if not self.input_custom_rect.collidepoint(event.pos) and not self.textarea_rect.collidepoint(event.pos):
                        self.keyboard.close()
                        self.input_custom_name.set_focus(False)
                        self.is_editing_prompt = False
                        return True

        # 3. Sự kiện cuộn chuột (MOUSEWHEEL) trong Textarea Prompt
        if event.type == pygame.MOUSEWHEEL:
            mouse_pos = getattr(event, "pos", pygame.mouse.get_pos())
            if self.textarea_rect.collidepoint(mouse_pos) or self.editor_card_rect.collidepoint(mouse_pos) or mouse_pos == (0, 0):
                self.max_scroll_line = self._calc_max_scroll()
                self.prompt_scroll_line = max(0, min(self.max_scroll_line, self.prompt_scroll_line - event.y))
                return True

        # 4. Sự kiện kéo vuốt cảm ứng (Touch Drag) trên Textarea
        if event.type == pygame.MOUSEMOTION:
            if getattr(self, "_is_touch_scrolling", False):
                dy = self._touch_start_y - event.pos[1]
                if abs(dy) > 6:
                    self._has_touch_dragged = True
                    delta_lines = dy // 18
                    self.max_scroll_line = self._calc_max_scroll()
                    self.prompt_scroll_line = max(0, min(self.max_scroll_line, self._touch_start_line + delta_lines))
                    return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if getattr(self, "_is_touch_scrolling", False):
                self._is_touch_scrolling = False
                if getattr(self, "_has_touch_dragged", False):
                    self._has_touch_dragged = False
                    return True

        # 5. Sự kiện nhấp chuột / chạm cảm ứng thông thường
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Nút Quay lại
            if self.back_btn_rect.collidepoint(event.pos):
                self.app_manager.switch_screen("face")
                return True

            # Nút Cuộn lên / xuống nhanh trong Textarea
            self.max_scroll_line = self._calc_max_scroll()
            if self.btn_scroll_up_rect.collidepoint(event.pos):
                self.prompt_scroll_line = max(0, self.prompt_scroll_line - 2)
                return True
            if self.btn_scroll_down_rect.collidepoint(event.pos):
                self.prompt_scroll_line = min(self.max_scroll_line, self.prompt_scroll_line + 2)
                return True

            # Bắt đầu theo dõi vuốt cảm ứng trong Textarea
            if self.textarea_rect.collidepoint(event.pos):
                self._is_touch_scrolling = True
                self._touch_start_y = event.pos[1]
                self._touch_start_line = self.prompt_scroll_line
                self._has_touch_dragged = False
                return True

            # Nút Bật bàn phím ảo cho Prompt
            if self.btn_open_keyboard_rect.collidepoint(event.pos):
                self.is_editing_prompt = True
                self.input_custom_name.set_focus(False)
                self.keyboard.open(self.prompt_adapter)
                return True

            # Nhấp vào danh sách chọn Role bên cột trái
            for i, r_rect in enumerate(self.role_rects):
                if r_rect.collidepoint(event.pos):
                    self.selected_role_id = PRESET_ROLES[i]["id"]
                    PersonaRepository.set_active_persona(self.selected_role_id)
                    self.prompt_text = PersonaRepository.get_system_instruction()
                    self.is_editing_prompt = False
                    self.prompt_scroll_line = 0

                    if self.selected_role_id == "custom":
                        # Nếu đang là tên mặc định ban đầu -> tự động xóa trắng để gõ tên mới ngay
                        if self.custom_role_name == "Vai trò Tùy chỉnh":
                            self.input_custom_name.value = ""
                        self.input_custom_name.set_focus(True)
                        self.keyboard.open(self.input_custom_name)
                    else:
                        self.input_custom_name.set_focus(False)
                        if self.keyboard.visible:
                            self.keyboard.close()
                    return True

            # Nhấp vào ô nhập tên Custom Role
            if self.selected_role_id == "custom" and self.input_custom_rect.collidepoint(event.pos):
                if self.input_custom_name.value.strip() == "Vai trò Tùy chỉnh":
                    self.input_custom_name.value = ""
                self.input_custom_name.set_focus(True)
                self.keyboard.open(self.input_custom_name)
                return True

            # Nhấp vào vùng soạn thảo prompt (Textarea)
            if self.textarea_rect.collidepoint(event.pos):
                self.is_editing_prompt = True
                self.input_custom_name.set_focus(False)
                # Tự động mở bàn phím ảo cho prompt nếu màn hình cảm ứng
                self.keyboard.open(self.prompt_adapter)
                return True
            else:
                if not (self.keyboard.visible and self.keyboard.rect.collidepoint(event.pos)):
                    self.is_editing_prompt = False

        # 5. Nhập liệu bàn phím vật lý khi ô custom role đang focus
        if self.selected_role_id == "custom" and self.input_custom_name.focused:
            if self.input_custom_name.handle_event(event):
                self.custom_role_name = self.input_custom_name.value
                return True

        # 6. Nhập liệu bàn phím vật lý khi đang sửa prompt trực tiếp
        if self.is_editing_prompt and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.prompt_text:
                    self.prompt_text = self.prompt_text[:-1]
                    self._ensure_cursor_visible()
                return True
            elif event.key == pygame.K_RETURN:
                if len(self.prompt_text) < MAX_PROMPT:
                    self.prompt_text += "\n"
                    self._ensure_cursor_visible()
                return True
            elif event.unicode and len(self.prompt_text) < MAX_PROMPT:
                self.prompt_text += event.unicode
                self._ensure_cursor_visible()
                return True

        # 7. Các nút bấm chính bên dưới
        if self.btn_apply.handle_event(event):
            return True
        if self.btn_preview.handle_event(event):
            return True
        if self.btn_reset.handle_event(event):
            return True

        return False

    def update(self):
        now = pygame.time.get_ticks()
        if now - self.last_cursor_toggle > 500:
            self.cursor_visible = not self.cursor_visible
            self.last_cursor_toggle = now

        if self.selected_role_id == "custom":
            self.input_custom_name.update()

        if self.keyboard.visible:
            self.keyboard.update()

        # Tự động ẩn thông báo Toast sau 2.8 giây
        if self.toast_message and now - self.toast_timer > 2800:
            self.toast_message = ""

    def draw(self, surface: pygame.Surface):
        surface.fill(self.PAGE_BG)
        mouse_pos = pygame.mouse.get_pos()

        # 1. Header: Nút Quay lại + Tiêu đề trang tiếng Việt
        hover_back = self.back_btn_rect.collidepoint(mouse_pos)
        back_col = self.TEXT_MAIN if not hover_back else Colors.PINE_GREEN
        pygame.draw.line(surface, back_col, (self.back_btn_rect.x + 8, self.back_btn_rect.centery), (self.back_btn_rect.x + 14, self.back_btn_rect.centery - 6), 2)
        pygame.draw.line(surface, back_col, (self.back_btn_rect.x + 8, self.back_btn_rect.centery), (self.back_btn_rect.x + 14, self.back_btn_rect.centery + 6), 2)
        back_text = self.theme.get_font(15, bold=True).render("Quay lại", True, back_col)
        surface.blit(back_text, (self.back_btn_rect.x + 20, self.back_btn_rect.centery - back_text.get_height() // 2))

        # Tiêu đề trung tâm tiếng Việt
        title_surf = self.theme.get_font(21, bold=True).render("Cấu hình Vai trò & Tính cách", True, self.TEXT_MAIN)
        surface.blit(title_surf, (400 - title_surf.get_width() // 2, 22))

        # Đường viền phân cách
        pygame.draw.line(surface, Colors.MIST_GRAY, (0, 60), (800, 60), 1)

        # 2. Cột trái: CÁC VAI TRÒ MẪU (PRESET ROLES)
        sec_title = self.theme.get_font(11, bold=True).render("CÁC VAI TRÒ MẪU", True, Colors.FOREST_GREEN)
        surface.blit(sec_title, (26, 68))

        for i, role in enumerate(PRESET_ROLES):
            rect = self.role_rects[i]
            is_active = (role["id"] == self.selected_role_id)

            # Nền card
            pygame.draw.rect(surface, self.CARD_BG, rect, border_radius=14)
            border_col = Colors.PINE_GREEN if is_active else self.CARD_BORDER
            border_w = 2 if is_active else 1
            pygame.draw.rect(surface, border_col, rect, width=border_w, border_radius=14)

            # Radio button
            radio_cx = rect.x + 22
            radio_cy = rect.centery
            radio_col = Colors.PINE_GREEN if is_active else Colors.SAGE_MUTED
            pygame.draw.circle(surface, radio_col, (radio_cx, radio_cy), 8, 2)
            if is_active:
                pygame.draw.circle(surface, Colors.PINE_GREEN, (radio_cx, radio_cy), 4)

            # Tên role & mô tả tiếng Việt
            role_title = self.custom_role_name if (role["id"] == "custom" and self.custom_role_name) else role["title"]
            name_surf = self.theme.get_font(13, bold=True).render(role_title, True, self.TEXT_MAIN)
            surface.blit(name_surf, (rect.x + 38, rect.y + 10))

            desc_surf = self.theme.get_font(11).render(role["desc"], True, self.TEXT_MUTED)
            surface.blit(desc_surf, (rect.x + 38, rect.y + 30))

        # Thanh input Tên vai trò
        if self.selected_role_id == "custom":
            lbl_inp = self.theme.get_font(11, bold=True).render("TÊN VAI TRÒ TÙY CHỈNH", True, Colors.FOREST_GREEN)
            surface.blit(lbl_inp, (26, 380))
            self.input_custom_name.draw(surface)
        else:
            placeholder_rect = self.input_custom_rect
            pygame.draw.rect(surface, Colors.CARD_BG, placeholder_rect, border_radius=12)
            pygame.draw.rect(surface, Colors.MIST_GRAY, placeholder_rect, width=1, border_radius=12)
            hint_txt = self.theme.get_font(13).render("Chọn Vai trò Tùy chỉnh để đặt tên...", True, Colors.SAGE_MUTED)
            surface.blit(hint_txt, (placeholder_rect.x + 14, placeholder_rect.centery - hint_txt.get_height() // 2))

        # 3. Cột phải: Card chi tiết cấu hình tiếng Việt
        pygame.draw.rect(surface, self.CARD_BG, self.editor_card_rect, border_radius=18)
        pygame.draw.rect(surface, self.CARD_BORDER, self.editor_card_rect, width=1, border_radius=18)

        # Tiêu đề trong card phải tiếng Việt
        card_t = self.theme.get_font(16, bold=True).render("Giọng điệu, Hành vi & Quy tắc hệ thống", True, self.TEXT_MAIN)
        surface.blit(card_t, (self.editor_card_rect.x + 16, self.editor_card_rect.y + 16))

        sub_rule = self.theme.get_font(12).render("Định hình cách Robot phản hồi và tương tác thông tin.", True, self.TEXT_MUTED)
        surface.blit(sub_rule, (self.editor_card_rect.x + 16, self.editor_card_rect.y + 40))

        # Nút [Soạn thảo] mở bàn phím ảo
        btn_kb_hover = self.btn_open_keyboard_rect.collidepoint(mouse_pos)
        kb_bg = (230, 240, 235) if btn_kb_hover else Colors.CARD_BG
        pygame.draw.rect(surface, kb_bg, self.btn_open_keyboard_rect, border_radius=8)
        pygame.draw.rect(surface, Colors.PINE_GREEN if btn_kb_hover else Colors.MIST_GRAY, self.btn_open_keyboard_rect, 1, border_radius=8)
        kb_text = self.theme.get_font(11, bold=True).render("Soạn thảo", True, Colors.FOREST_GREEN)
        surface.blit(kb_text, kb_text.get_rect(center=self.btn_open_keyboard_rect.center))

        # Khung Textarea chứa prompt
        pygame.draw.rect(surface, Colors.CARD_BG, self.textarea_rect, border_radius=14)
        area_border = self.ACCENT_GREEN if self.is_editing_prompt else Colors.MIST_GRAY
        area_width = 2 if self.is_editing_prompt else 1
        pygame.draw.rect(surface, area_border, self.textarea_rect, width=area_width, border_radius=14)

        # Render nhiều dòng prompt (có cuộn dòng)
        self._draw_prompt_lines(surface)

        # Đếm ký tự & chuẩn ngôn ngữ
        char_count = f"{len(self.prompt_text)} / {MAX_PROMPT:,} ký tự  •  Tiếng Việt UTF-8"
        count_surf = self.theme.get_font(11).render(char_count, True, Colors.TEXT_MUTED)
        surface.blit(count_surf, (self.textarea_rect.x, self.editor_card_rect.bottom - 28))

        # Trạng thái lưu
        status_label = "Đang soạn thảo..." if self.is_editing_prompt else "Đã lưu vào bộ nhớ"
        auto_surf = self.theme.get_font(11).render(status_label, True, Colors.TEXT_MUTED)
        surface.blit(auto_surf, (self.btn_reset.rect.x, self.textarea_rect.bottom + 8))

        # Nút bấm hành động (Đặt lại, Xem trước, Lưu & Áp dụng)
        self.btn_reset.draw(surface)
        self.btn_preview.draw(surface)
        self.btn_apply.draw(surface)

        # 4. Thông báo Toast nổi bật
        if self.toast_message:
            toast_surf = self.theme.get_font(13, bold=True).render(self.toast_message, True, Colors.COLOR_WHITE)
            tw, th = toast_surf.get_width() + 32, 38
            t_rect = pygame.Rect(400 - tw // 2, 434, tw, th)
            pygame.draw.rect(surface, self.SUCCESS_COLOR, t_rect, border_radius=19)
            surface.blit(toast_surf, toast_surf.get_rect(center=t_rect.center))

        # 5. Cửa sổ nổi xem trước (Preview Modal)
        if self.show_preview_modal:
            self._draw_preview_modal(surface)

        # 6. Bàn phím ảo cảm ứng và Floating Input Bar nếu đang mở
        if self.keyboard.visible and not self.show_preview_modal:
            self._draw_keyboard_floating_bar(surface)
            self.keyboard.draw(surface)

    def _draw_prompt_lines(self, surface: pygame.Surface):
        """Vẽ nội dung prompt trong textarea có ngắt dòng và cuộn dòng mượt mà."""
        font = self.theme.get_font(13)
        line_height = 20
        max_w = self.textarea_rect.width - 36
        visible_lines = max(1, (self.textarea_rect.height - 24) // line_height)

        lines = self._get_wrapped_lines()
        total_lines = len(lines)
        self.max_scroll_line = max(0, total_lines - visible_lines)
        self.prompt_scroll_line = max(0, min(self.max_scroll_line, self.prompt_scroll_line))

        # Cắt xén vùng vẽ bằng clip rect
        old_clip = surface.get_clip()
        clip_rect = pygame.Rect(self.textarea_rect.x + 4, self.textarea_rect.y + 4, self.textarea_rect.width - 24, self.textarea_rect.height - 8)
        surface.set_clip(clip_rect)

        start_idx = self.prompt_scroll_line
        end_idx = min(total_lines, start_idx + visible_lines + 1)
        y = self.textarea_rect.y + 12
        last_line_x = self.textarea_rect.x + 12

        for i in range(start_idx, end_idx):
            line = lines[i]
            if line:
                ts = font.render(line, True, self.TEXT_MAIN)
                surface.blit(ts, (self.textarea_rect.x + 12, y))
                last_line_x = self.textarea_rect.x + 12 + ts.get_width() + 2
            else:
                last_line_x = self.textarea_rect.x + 12

            # Con trỏ nhấp nháy ở cuối dòng cuối cùng
            if self.is_editing_prompt and self.cursor_visible and i == total_lines - 1:
                pygame.draw.line(surface, self.TEXT_MAIN, (last_line_x, y + 2), (last_line_x, y + 17), 2)

            y += line_height

        surface.set_clip(old_clip)

        # Vẽ thanh cuộn mảnh nếu có nhiều dòng
        if self.max_scroll_line > 0:
            track_h = self.textarea_rect.height - 54
            thumb_h = max(16, int(track_h * (visible_lines / total_lines)))
            thumb_y = self.textarea_rect.y + 28 + int((track_h - thumb_h) * (self.prompt_scroll_line / self.max_scroll_line))
            thumb_x = self.textarea_rect.right - 14

            # Nút cuộn lên ▲
            pygame.draw.polygon(surface, Colors.SAGE_MUTED, [
                (self.btn_scroll_up_rect.centerx, self.btn_scroll_up_rect.y + 4),
                (self.btn_scroll_up_rect.x + 3, self.btn_scroll_up_rect.bottom - 4),
                (self.btn_scroll_up_rect.right - 3, self.btn_scroll_up_rect.bottom - 4)
            ])
            # Nút cuộn xuống ▼
            pygame.draw.polygon(surface, Colors.SAGE_MUTED, [
                (self.btn_scroll_down_rect.centerx, self.btn_scroll_down_rect.bottom - 4),
                (self.btn_scroll_down_rect.x + 3, self.btn_scroll_down_rect.y + 4),
                (self.btn_scroll_down_rect.right - 3, self.btn_scroll_down_rect.y + 4)
            ])
            # Thanh trượt thumb
            pygame.draw.rect(surface, Colors.MIST_GRAY, (thumb_x, thumb_y, 6, thumb_h), border_radius=3)

    def _draw_keyboard_floating_bar(self, surface: pygame.Surface):
        """Vẽ thanh nổi phía trên bàn phím ảo để người dùng luôn thấy rõ những gì đang gõ."""
        bar_y = self.keyboard.rect.y - 46
        bar_w = 760
        bar_rect = pygame.Rect(20, bar_y, bar_w, 42)

        # Nền banner nổi viền Pine Green
        pygame.draw.rect(surface, Colors.CARD_BG, bar_rect, border_radius=12)
        pygame.draw.rect(surface, Colors.PINE_GREEN, bar_rect, width=1, border_radius=12)

        if self.keyboard.active_input is self.input_custom_name:
            tag = self.theme.get_font(12, bold=True).render("Tên vai trò:", True, Colors.PINE_GREEN)
            surface.blit(tag, (bar_rect.x + 14, bar_rect.centery - tag.get_height() // 2))

            val = self.input_custom_name.value
            txt = self.theme.get_font(14, bold=True).render(val if val else "...", True, self.TEXT_MAIN)
            surface.blit(txt, (bar_rect.x + 14 + tag.get_width() + 8, bar_rect.centery - txt.get_height() // 2))

            # Nút Xóa hết
            btn_clear = pygame.Rect(bar_rect.right - 176, bar_rect.y + 4, 80, 34)
            pygame.draw.rect(surface, (252, 242, 242), btn_clear, border_radius=8)
            pygame.draw.rect(surface, (230, 160, 160), btn_clear, width=1, border_radius=8)
            c_txt = self.theme.get_font(11, bold=True).render("Xóa hết", True, (190, 70, 70))
            surface.blit(c_txt, c_txt.get_rect(center=btn_clear.center))

            # Nút Hoàn tất
            btn_done = pygame.Rect(bar_rect.right - 88, bar_rect.y + 4, 80, 34)
            pygame.draw.rect(surface, Colors.PINE_GREEN, btn_done, border_radius=8)
            d_txt = self.theme.get_font(12, bold=True).render("Xong", True, Colors.COLOR_WHITE)
            surface.blit(d_txt, d_txt.get_rect(center=btn_done.center))

        elif self.keyboard.active_input is self.prompt_adapter:
            tag = self.theme.get_font(12, bold=True).render("Đang soạn Prompt:", True, Colors.PINE_GREEN)
            surface.blit(tag, (bar_rect.x + 14, bar_rect.centery - tag.get_height() // 2))

            # Hiển thị 45 ký tự cuối cùng của prompt
            val_tail = self.prompt_text[-42:].replace("\n", " [Enter] ") if self.prompt_text else "..."
            txt = self.theme.get_font(13).render(val_tail, True, self.TEXT_MAIN)
            surface.blit(txt, (bar_rect.x + 14 + tag.get_width() + 8, bar_rect.centery - txt.get_height() // 2))

            # Nút [Dòng mới]
            btn_nl = pygame.Rect(bar_rect.right - 180, bar_rect.y + 4, 86, 34)
            pygame.draw.rect(surface, (230, 240, 235), btn_nl, border_radius=8)
            pygame.draw.rect(surface, Colors.PINE_GREEN, btn_nl, width=1, border_radius=8)
            nl_txt = self.theme.get_font(11, bold=True).render("Dòng mới", True, Colors.FOREST_GREEN)
            surface.blit(nl_txt, nl_txt.get_rect(center=btn_nl.center))

            # Nút [Xong]
            btn_done = pygame.Rect(bar_rect.right - 88, bar_rect.y + 4, 80, 34)
            pygame.draw.rect(surface, Colors.PINE_GREEN, btn_done, border_radius=8)
            d_txt = self.theme.get_font(12, bold=True).render("Xong", True, Colors.COLOR_WHITE)
            surface.blit(d_txt, d_txt.get_rect(center=btn_done.center))

    def _draw_preview_modal(self, surface: pygame.Surface):
        """Vẽ cửa sổ Modal Xem trước Vai trò & Tính cách có hỗ trợ cuộn văn bản."""
        # 1. Lớp phủ đen trong suốt làm mờ nền
        overlay = pygame.Surface((800, 480), pygame.SRCALPHA)
        overlay.fill((24, 61, 48, 160))
        surface.blit(overlay, (0, 0))

        # 2. Khung Card Modal màu trắng
        pygame.draw.rect(surface, Colors.CARD_BG, self.modal_rect, border_radius=20)
        pygame.draw.rect(surface, self.CARD_BORDER, self.modal_rect, width=1, border_radius=20)

        # 3. Header Modal
        m_top = self.modal_rect.y
        m_x = self.modal_rect.x
        m_w = self.modal_rect.width

        # Tiêu đề modal
        m_title = self.theme.get_font(18, bold=True).render("Xem trước Vai trò & Tính cách", True, self.TEXT_MAIN)
        surface.blit(m_title, (m_x + 24, m_top + 18))

        # Nút đóng [X] dạng vector
        pygame.draw.rect(surface, self.CARD_BORDER, self.modal_close_rect, border_radius=15)
        cx, cy = self.modal_close_rect.center
        pygame.draw.line(surface, self.TEXT_MAIN, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
        pygame.draw.line(surface, self.TEXT_MAIN, (cx - 5, cy + 5), (cx + 5, cy - 5), 2)

        # Đường kẻ phân cách
        pygame.draw.line(surface, self.CARD_BORDER, (m_x, m_top + 52), (m_x + m_w, m_top + 52), 1)

        # 4. Nội dung chi tiết
        role_name = self._get_current_role_title()
        
        # Nhãn Tên vai trò
        lbl_r = self.theme.get_font(12, bold=True).render("TÊN VAI TRÒ ĐANG CHỌN:", True, self.ACCENT_GREEN)
        surface.blit(lbl_r, (m_x + 24, m_top + 64))

        val_r = self.theme.get_font(16, bold=True).render(role_name, True, self.TEXT_MAIN)
        surface.blit(val_r, (m_x + 24, m_top + 84))

        # Huy hiệu trạng thái
        badge_rect = pygame.Rect(m_x + 24 + val_r.get_width() + 12, m_top + 84, 96, 24)
        pygame.draw.rect(surface, (230, 240, 235), badge_rect, border_radius=12)
        b_txt = self.theme.get_font(11, bold=True).render("Sẵn sàng áp dụng", True, self.ACCENT_GREEN)
        surface.blit(b_txt, b_txt.get_rect(center=badge_rect.center))

        # Nhãn Quy tắc hệ thống
        lbl_p = self.theme.get_font(12, bold=True).render("NỘI DUNG QUY TẮC & HƯỚNG DẪN HỆ THỐNG:", True, Colors.SAGE_MUTED)
        surface.blit(lbl_p, (m_x + 24, m_top + 120))

        # Khung văn bản quy tắc trong Modal
        pygame.draw.rect(surface, self.PAGE_BG, self.modal_prompt_box, border_radius=12)
        pygame.draw.rect(surface, self.CARD_BORDER, self.modal_prompt_box, width=1, border_radius=12)

        # Render văn bản prompt trong modal có ngắt dòng và cuộn
        font = self.theme.get_font(12)
        line_h = 18
        max_pw = self.modal_prompt_box.width - 24
        p_lines = self._wrap_text(self.prompt_text, max_pw, font)
        total_p_lines = len(p_lines)
        vis_m_lines = max(1, (self.modal_prompt_box.height - 20) // line_h)
        max_m_scroll = max(0, total_p_lines - vis_m_lines)
        start_m = min(max_m_scroll, self.preview_scroll_y // line_h)

        old_clip = surface.get_clip()
        m_clip = pygame.Rect(self.modal_prompt_box.x + 4, self.modal_prompt_box.y + 4, self.modal_prompt_box.width - 8, self.modal_prompt_box.height - 8)
        surface.set_clip(m_clip)

        py = self.modal_prompt_box.y + 12
        for i in range(start_m, min(total_p_lines, start_m + vis_m_lines + 1)):
            line = p_lines[i]
            if line:
                surface.blit(font.render(line, True, self.TEXT_MAIN), (self.modal_prompt_box.x + 12, py))
            py += line_h

        surface.set_clip(old_clip)

        # 5. Footer Modal: Nút "Đóng" và nút "Áp dụng"
        pygame.draw.line(surface, self.CARD_BORDER, (m_x, self.modal_rect.bottom - 66), (m_x + m_w, self.modal_rect.bottom - 66), 1)
        self.modal_btn_close.draw(surface)
        self.modal_btn_apply.draw(surface)
