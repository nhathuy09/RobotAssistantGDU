import pygame
from typing import Callable, List, Optional, Tuple
from display.components.base_widget import BaseWidget
from display.theme import Colors



VOWEL_MAP = {
    "a": ("a", "á", "à", "ả", "ã", "ạ"),
    "ă": ("ă", "ắ", "ằ", "ẳ", "ẵ", "ặ"),
    "â": ("â", "ấ", "ầ", "ẩ", "ẫ", "ậ"),
    "e": ("e", "é", "è", "ẻ", "ẽ", "ẹ"),
    "ê": ("ê", "ế", "ề", "ể", "ễ", "ệ"),
    "i": ("i", "í", "ì", "ỉ", "ĩ", "ị"),
    "o": ("o", "ó", "ò", "ỏ", "õ", "ọ"),
    "ô": ("ô", "ố", "ồ", "ổ", "ỗ", "ộ"),
    "ơ": ("ơ", "ớ", "ờ", "ở", "ỡ", "ợ"),
    "u": ("u", "ú", "ù", "ủ", "ũ", "ụ"),
    "ư": ("ư", "ứ", "ừ", "ử", "ữ", "ự"),
    "y": ("y", "ý", "ỳ", "ỷ", "ỹ", "ỵ"),
}

REVERSE_VOWEL = {}
for base_char, variants in VOWEL_MAP.items():
    for tone_idx, c in enumerate(variants):
        REVERSE_VOWEL[c] = (base_char, tone_idx)
        REVERSE_VOWEL[c.upper()] = (base_char.upper(), tone_idx)

TONE_KEYS = {"s": 1, "f": 2, "r": 3, "x": 4, "j": 5, "z": 0}


def _remove_tone_from_word(w: str) -> Tuple[str, int]:
    new_chars = []
    current_tone = 0
    for ch in w:
        if ch in REVERSE_VOWEL:
            base, t = REVERSE_VOWEL[ch]
            new_chars.append(base)
            if t > 0:
                current_tone = t
        else:
            new_chars.append(ch)
    return "".join(new_chars), current_tone


def _find_vowel_position(base_w: str) -> int:
    w_lower = base_w.lower()
    vowel_indices = [i for i, c in enumerate(w_lower) if c in VOWEL_MAP or c in REVERSE_VOWEL]
    if not vowel_indices:
        return -1
    if len(vowel_indices) == 1:
        return vowel_indices[0]

    # Ưu tiên nguyên âm có mũ / móc: ê, ơ, ư, â, ô, ă
    for i in vowel_indices:
        c_base, _ = REVERSE_VOWEL.get(base_w[i], (w_lower[i], 0))
        if c_base.lower() in ("ê", "ơ", "ư", "â", "ô", "ă"):
            return i

    # Xét cụm nguyên âm đặc biệt
    if len(vowel_indices) >= 2:
        pair = w_lower[vowel_indices[0]] + w_lower[vowel_indices[1]]
        if pair == "uy":
            prev_char = w_lower[vowel_indices[0] - 1] if vowel_indices[0] > 0 else ""
            return vowel_indices[1] if prev_char == "q" else vowel_indices[0]
        if pair in ("oa", "oe", "ia", "ua", "ưa"):
            has_ending = vowel_indices[-1] < len(base_w) - 1
            return vowel_indices[1] if has_ending else vowel_indices[0]

    has_ending_consonant = vowel_indices[-1] < len(base_w) - 1
    return vowel_indices[-1] if has_ending_consonant else vowel_indices[0]


def _apply_tone(word: str, tone_idx: int) -> str:
    base_w, _ = _remove_tone_from_word(word)
    if tone_idx == 0:
        return base_w
    pos = _find_vowel_position(base_w)
    if pos == -1:
        return word
    chars = list(base_w)
    ch = chars[pos]
    is_upper = ch.isupper()
    ch_lower = ch.lower()
    if ch_lower in VOWEL_MAP:
        new_ch = VOWEL_MAP[ch_lower][tone_idx]
        chars[pos] = new_ch.upper() if is_upper else new_ch
    return "".join(chars)


def process_telex_word(word: str, key: str) -> str:
    """Xử lý gõ thêm 1 ký tự vào từ hiện tại theo quy tắc Telex tiếng Việt."""
    if not word:
        if key.lower() == "w":
            return "Ư" if key.isupper() else "ư"
        return key

    k_lower = key.lower()

    # 1. Dấu thanh: s, f, r, x, j, z
    if k_lower in TONE_KEYS:
        target_tone = TONE_KEYS[k_lower]
        base_w, cur_tone = _remove_tone_from_word(word)
        has_vowel = any(c in VOWEL_MAP or c in REVERSE_VOWEL for c in base_w.lower())
        if has_vowel:
            if cur_tone == target_tone:
                # Gõ phím dấu lần 2 -> khôi phục từ không dấu + thêm ký tự phím
                return base_w + key
            return _apply_tone(word, target_tone)

    # 2. Biến đổi ký tự kép (aa, aw, ee, oo, ow, uw, dd, w)
    w_lower = word.lower()
    last_ch = word[-1]
    last_lower = last_ch.lower()

    if last_lower == "a" and k_lower == "a":
        return word[:-1] + ("Â" if last_ch.isupper() else "â")
    elif last_lower == "a" and k_lower == "w":
        return word[:-1] + ("Ă" if last_ch.isupper() else "ă")
    elif last_lower == "e" and k_lower == "e":
        return word[:-1] + ("Ê" if last_ch.isupper() else "ê")
    elif last_lower == "o" and k_lower == "o":
        return word[:-1] + ("Ô" if last_ch.isupper() else "ô")
    elif last_lower == "o" and k_lower == "w":
        return word[:-1] + ("Ơ" if last_ch.isupper() else "ơ")
    elif last_lower == "u" and k_lower == "w":
        return word[:-1] + ("Ư" if last_ch.isupper() else "ư")
    elif w_lower.endswith("uo") and k_lower == "w":
        is_upper = word[-2:].isupper()
        return word[:-2] + ("ƯƠ" if is_upper else "ươ")
    elif last_lower == "d" and k_lower == "d":
        return word[:-1] + ("Đ" if last_ch.isupper() else "đ")
    elif k_lower == "w":
        return word + ("Ư" if key.isupper() else "ư")

    return word + key


# ==========================================================
# LỚP BÀN PHÍM ẢO CẢM ỨNG (VIRTUAL KEYBOARD)
# ==========================================================

class VirtualKeyboard(BaseWidget):
    """Component bàn phím ảo cảm ứng có bộ gõ tiếng Việt Telex và tính năng nhấn giữ lặp phím."""

    HOLD_INITIAL_DELAY_MS = 380  # Thời gian giữ trước khi bắt đầu lặp phím
    HOLD_REPEAT_INTERVAL_MS = 65  # Tần số lặp phím khi giữ (mỗi 65ms lặp 1 lần)

    def __init__(
        self,
        top_y: int = 220,
        height: int = 260,
        width: int = 800,
        on_submit: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(pygame.Rect(0, top_y, width, height))
        self.on_submit = on_submit
        self.on_cancel = on_cancel
        self.active_input = None

        self.is_numeric = False
        self.is_shift = False
        self.vietnamese_mode = True  # Mặc định bật bộ gõ tiếng Việt Telex

        # Cơ chế nhấn giữ lặp phím (Key repeat / hold)
        self.held_key: Optional[str] = None
        self.held_time: int = 0
        self.last_repeat_time: int = 0

        self.font = pygame.font.SysFont("Segoe UI", 16, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 13, bold=True)
        self.font_tag = pygame.font.SysFont("Segoe UI", 11, bold=True)

        self._key_rects: List[Tuple[pygame.Rect, str, str]] = []  # (rect, key_code, label)
        self.visible = False

    def open(self, target_input=None):
        self.active_input = target_input
        self.visible = True
        self.is_shift = False
        self.is_numeric = False
        self.held_key = None

    def close(self):
        self.visible = False
        self.held_key = None
        if self.active_input is not None and hasattr(self.active_input, "set_focus"):
            self.active_input.set_focus(False)
        self.active_input = None

    def update(self):
        """Cập nhật lặp phím khi người dùng nhấn giữ lâu trên màn hình cảm ứng."""
        if not self.visible or not self.held_key:
            return

        now = pygame.time.get_ticks()
        if now - self.held_time > self.HOLD_INITIAL_DELAY_MS:
            if now - self.last_repeat_time > self.HOLD_REPEAT_INTERVAL_MS:
                self._on_press_key(self.held_key)
                self.last_repeat_time = now

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for r, code, _ in self._key_rects:
                if r.collidepoint(event.pos):
                    # Kích hoạt phím ngay lập tức và bắt đầu theo dõi nhấn giữ
                    self.held_key = code
                    self.held_time = pygame.time.get_ticks()
                    self.last_repeat_time = self.held_time
                    self._on_press_key(code)
                    return True

            if self.rect.collidepoint(event.pos):
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.held_key = None

        elif event.type == pygame.MOUSEMOTION:
            if self.held_key:
                # Nếu ngón tay trượt ra ngoài vùng phím đang giữ thì huỷ lặp
                found = False
                for r, code, _ in self._key_rects:
                    if code == self.held_key and r.collidepoint(event.pos):
                        found = True
                        break
                if not found:
                    self.held_key = None

        return False

    def _on_press_key(self, code: str):
        target = self.active_input

        # Các phím chức năng đặc biệt
        if code == "cancel":
            self.close()
            if self.on_cancel:
                self.on_cancel()
            return

        elif code == "submit":
            if target is not None and hasattr(target, "on_submit") and target.on_submit:
                target.on_submit(target.value)
            if self.on_submit:
                self.on_submit()
            self.close()
            return

        elif code == "shift":
            self.is_shift = not self.is_shift
            return

        elif code == "123":
            self.is_numeric = not self.is_numeric
            self.is_shift = False
            return

        elif code == "lang":
            # Chuyển đổi bộ gõ Tiếng Việt / Tiếng Anh
            self.vietnamese_mode = not self.vietnamese_mode
            return

        elif code == "clear":
            # Xóa toàn bộ nội dung trong ô nhập chỉ bằng 1 chạm
            if target is not None:
                target.value = ""
                if hasattr(target, "on_text_change") and target.on_text_change:
                    target.on_text_change("")
            return

        if target is None:
            return

        # Phím Xóa lùi (Backspace / DEL)
        if code == "back":
            if target.value:
                target.value = target.value[:-1]
                if hasattr(target, "on_text_change") and target.on_text_change:
                    target.on_text_change(target.value)
            return

        # Phím khoảng trắng (Space)
        if code == "space":
            if target.max_length is None or len(target.value) < target.max_length:
                target.value += " "
                if hasattr(target, "on_text_change") and target.on_text_change:
                    target.on_text_change(target.value)
            return

        # Ký tự thông thường
        new_char = code.upper() if self.is_shift else code
        if getattr(target, "is_numeric", False):
            new_char = "".join(c for c in new_char if c.isdigit())

        if not new_char:
            return

        # Nếu đang ở chế độ gõ tiếng Việt Telex và không phải bàn phím số
        if self.vietnamese_mode and not self.is_numeric and not getattr(target, "is_numeric", False):
            # Tách từ cuối cùng đang gõ
            val = target.value
            last_space = max(val.rfind(" "), val.rfind("\n"), val.rfind("\t"))
            if last_space == -1:
                prefix = ""
                cur_word = val
            else:
                prefix = val[: last_space + 1]
                cur_word = val[last_space + 1 :]

            new_word = process_telex_word(cur_word, new_char)
            candidate_val = prefix + new_word

            if target.max_length is not None and len(candidate_val) > target.max_length:
                return

            target.value = candidate_val
        else:
            if target.max_length is not None and len(target.value) >= target.max_length:
                return
            target.value += new_char

        if hasattr(target, "on_text_change") and target.on_text_change:
            target.on_text_change(target.value)

        # Tự động tắt shift sau khi gõ 1 ký tự
        if self.is_shift:
            self.is_shift = False

    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        self._key_rects.clear()
        mouse_pos = pygame.mouse.get_pos()

        # Nền bàn phím màu Mist Gray dịu mát
        pygame.draw.rect(surface, (235, 239, 236), self.rect)
        pygame.draw.line(surface, Colors.MIST_GRAY, (0, self.rect.y), (self.rect.w, self.rect.y), 1)

        if self.is_numeric:
            rows = [
                ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
                ["-", "/", ":", ";", "(", ")", "$", "&", "@", '"'],
                ["shift", ".", ",", "?", "!", "'", "#", "back"],
            ]
        else:
            rows = [
                ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
                ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
                ["shift", "z", "x", "c", "v", "b", "n", "m", "back"],
            ]

        key_h = 44
        key_gap = 5
        curr_y = self.rect.y + 10

        for row in rows:
            key_w = 60
            widths = [86 if k in ("shift", "back") else key_w for k in row]
            total_w = sum(widths) + key_gap * (len(row) - 1)
            curr_x = (self.rect.w - total_w) // 2

            for k, w in zip(row, widths):
                kr = pygame.Rect(curr_x, curr_y, w, key_h)
                label = k.upper() if (self.is_shift and len(k) == 1) else k
                if k == "shift":
                    label = "CAPS"
                elif k == "back":
                    label = "DEL"
                self._draw_key(surface, kr, k, label, mouse_pos)
                curr_x += w + key_gap
            curr_y += key_h + key_gap

        # Hàng phím dưới cùng: ?123, VIE/ENG, space, Xóa hết, Hủy, Xong
        sym_w = 66
        lang_w = 66
        space_w = 260
        clear_w = 78
        cancel_w = 74
        submit_w = 100
        total_bot = sym_w + lang_w + space_w + clear_w + cancel_w + submit_w + key_gap * 5
        curr_x = (self.rect.w - total_bot) // 2

        # 1. Nút ?123 / ABC
        r_sym = pygame.Rect(curr_x, curr_y, sym_w, key_h)
        self._draw_key(surface, r_sym, "123", "ABC" if self.is_numeric else "?123", mouse_pos)
        curr_x += sym_w + key_gap

        # 2. Nút chuyển ngôn ngữ VIE / ENG
        r_lang = pygame.Rect(curr_x, curr_y, lang_w, key_h)
        lang_bg = (220, 238, 228) if self.vietnamese_mode else Colors.COLOR_WHITE
        lang_fg = Colors.PINE_GREEN if self.vietnamese_mode else Colors.TEXT_MUTED
        self._draw_key(surface, r_lang, "lang", "VIE" if self.vietnamese_mode else "ENG", mouse_pos, bg=lang_bg, fg=lang_fg)
        curr_x += lang_w + key_gap

        # 3. Phím Khoảng trắng (Space)
        r_sp = pygame.Rect(curr_x, curr_y, space_w, key_h)
        space_label = "khoảng trắng" if self.vietnamese_mode else "khoảng trắng"
        self._draw_key(surface, r_sp, "space", space_label, mouse_pos)
        curr_x += space_w + key_gap

        # 4. Nút Xóa hết (Clear all)
        r_clr = pygame.Rect(curr_x, curr_y, clear_w, key_h)
        self._draw_key(surface, r_clr, "clear", "Xóa hết", mouse_pos, fg=(190, 80, 80))
        curr_x += clear_w + key_gap

        # 5. Nút Hủy
        r_can = pygame.Rect(curr_x, curr_y, cancel_w, key_h)
        self._draw_key(surface, r_can, "cancel", "Hủy", mouse_pos, fg=Colors.COLOR_DANGER)
        curr_x += cancel_w + key_gap

        # 6. Nút Xong (Submit)
        r_sub = pygame.Rect(curr_x, curr_y, submit_w, key_h)
        self._draw_key(
            surface,
            r_sub,
            "submit",
            "Xong",
            mouse_pos,
            bg=Colors.PINE_GREEN,
            fg=Colors.COLOR_WHITE,
        )

    def _draw_key(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        code: str,
        label: str,
        mouse_pos: Tuple[int, int],
        bg=None,
        fg=None,
    ):
        hovered = rect.collidepoint(mouse_pos)
        is_being_held = (self.held_key == code)

        if is_being_held:
            fill = (210, 225, 218)
        elif hovered:
            fill = (240, 245, 242)
        else:
            fill = bg or Colors.COLOR_WHITE

        text_col = fg or Colors.FOREST_GREEN

        if code == "shift" and self.is_shift:
            fill = (215, 232, 224)

        pygame.draw.rect(surface, fill, rect, border_radius=8)
        border_col = Colors.PINE_GREEN if (hovered or is_being_held) else Colors.MIST_GRAY
        pygame.draw.rect(surface, border_col, rect, 1, border_radius=8)

        use_font = self.font_small if len(label) > 2 else self.font
        ts = use_font.render(label, True, text_col)
        surface.blit(ts, ts.get_rect(center=rect.center))

        self._key_rects.append((rect, code, label))
