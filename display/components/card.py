import pygame
from typing import Optional, Tuple
from display.components.base_widget import BaseWidget
from display.theme import Colors, Theme
class Card(BaseWidget):
    def __init__(self,
                 rect:pygame.Rect,
                 theme:Theme,
                 title: Optional[str] = None,
                 description: Optional[str] = None,
                 visible: bool = True,
                 bg_color: Tuple[int, int, int] = Colors.CARD_BG,
                 border_color: Tuple[int, int, int] = Colors.CARD_BORDER,
                 border_radius: int = 14,
                 padding: int = 16,
                 title_color: Tuple[int, int, int] = Colors.TEXT_DARK,
                 description_color: Tuple[int, int, int] = Colors.TEXT_MUTED,
                 title_font: Optional[pygame.font.Font] = None,
                 description_font: Optional[pygame.font.Font] = None,
                 enabled: bool = True,
                 ):
        super().__init__(rect)
        self.title = title
        self.description = description

        self.bg_color = bg_color
        self.border_color = border_color
        self.border_radius = border_radius
        self.padding = padding

        self.title_color = title_color
        self.description_color = description_color

        self.title_font = title_font
        self.description_font = description_font
        self.theme = theme
    def draw(self,surface:pygame.Surface):
        if not  self.visible:
            return
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=self.border_radius)
        if self.border_color is not None:
            pygame.draw.rect(surface, self.border_color, self.rect, 1, border_radius=self.border_radius)
        y = self.rect.y + self.padding
        if self.title:
            font = self.title_font
            if font is None and self.theme is not None:
                font = self.theme.get_font(15, bold=True)
            if font is not None:
                title_surface = font.render(self.title, True, self.title_color)
                surface.blit(title_surface, (self.rect.x + self.padding, y))
                y += title_surface.get_height() + 8
        if self.description:
            font = self.description_font
            if font is None and self.theme is not None:
                font = self.theme.get_font(13)
            if font is not None:
                description_surface = font.render(self.description, True, self.description_color)
                surface.blit(description_surface, (self.rect.x + self.padding, y))