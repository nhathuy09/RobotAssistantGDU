import pygame 
from typing import Tuple, Optional,Callable
from display.components.base_widget import BaseWidget
from display.theme import Colors, Theme

class Button(BaseWidget):
    def __init__(self,rect:pygame.Rect,
                 theme: Theme,
                 text:str,
                 visible:bool=True,
                 font:Optional[pygame.font.Font]=None,
                 on_click:Optional[Callable[[],None]]=None,
                 primary:bool=True,
                 bg_color: Optional[Tuple[int, int, int]] = None,
                 fg_color: Optional[Tuple[int, int, int]] = None,
                 border_color: Optional[Tuple[int, int, int]] = None, 
                 border_radius: int = 12, 
                 icon: Optional[str] = None,
                 enabled:bool=True):
        super().__init__(rect,visible,enabled)
        self.text=text
        self.theme=theme
        self.font=font
        self.on_click=on_click
        self.primary=primary
        self.border_radius=border_radius
        self.icon=icon
        if bg_color:
            self.bg_color=bg_color
        else:
            self.bg_color=Colors.BTN_PRIMARY if primary else Colors.CARD_BG
        
        if fg_color:
            self.fg_color=fg_color
        else:
            self.fg_color=Colors.COLOR_TEETH if primary else Colors.TEXT_DARK
        
        if border_color:
            self.border_color=border_color
        else:
            self.border_color=bg_color if primary else Colors.CARD_BORDER
        self.is_hovered=False
        self.is_pressed=False
    
    def handle_event(self,event:pygame.event.Event)->bool:
        if not self.visible or not self.enabled:
            self.is_pressed = False
            self.is_hovered = False
            return False
        if event.type==pygame.MOUSEMOTION:
            self.is_hovered=self.rect.collidepoint(event.pos)
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if self.rect.collidepoint(event.pos):
                self.is_pressed=True
                return True
        elif event.type==pygame.MOUSEBUTTONUP and event.button==1:
            was_pressed = self.is_pressed
            self.is_pressed = False
            if was_pressed:
                if self.rect.collidepoint(event.pos):
                    if self.on_click:
                        self.on_click()
                return True
        return False
    def draw(self,surface:pygame.Surface):
        if not self.visible:
            return
        color=self.bg_color
        if not self.enabled:
            color=Colors.COLOR_C8CCC8
        if self.is_pressed:
            color=Colors.BTN_PRIMARY_HOVER
        if self.is_hovered:
            color=Colors.BTN_PRIMARY_HOVER
        pygame.draw.rect(surface,color,self.rect,border_radius=self.border_radius)
        if self.border_color:
            pygame.draw.rect(surface,self.border_color,self.rect,1,border_radius=self.border_radius)
        if self.text and self.font:
            font = self.font or self.theme.get_font(14, bold=True)
            text_surf = font.render(self.text, True, self.fg_color)
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)