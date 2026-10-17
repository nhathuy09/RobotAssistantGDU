import pygame
from typing import Tuple, Optional

class BaseWidget:
    def __init__(self,rect: pygame.Rect,visible: bool = True, enabled: bool = True):
        self.rect = pygame.Rect(rect)
        self.visible = visible
        self.enabled = enabled
        self.focused=False 
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Xử lý sự kiện pygame. Trả về True nếu sự kiện đã được tiêu thụ (consumed).
        """
        if not self.visible or not self.enabled:
            return False
        return False

    def update(self):
        """Cập nhật logic theo từng frame (animation, blinking,...)."""
        pass

    def draw(self, surface: pygame.Surface):
        """Vẽ component lên surface."""
        pass

    def contains(self, pos: Tuple[int, int]) -> bool:
        """Kiểm tra toạ độ pos có nằm trong rect không."""
        return self.visible and self.rect.collidepoint(pos)

    def set_focus(self, focus: bool):
        self.focused = focus
