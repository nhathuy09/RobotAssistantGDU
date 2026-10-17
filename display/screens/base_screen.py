import pygame
from typing import Optional

class BaseScreen:
    def __init__(self,app_manager):
        self.app_manager=app_manager
        self.theme=app_manager.theme
    def on_enter(self):
        pass
    def on_leave(self):
        pass
    def handle_event(self,event:pygame.event.Event) -> bool:
        return False
    def update(self):
        pass
    def draw(self,surface:pygame.Surface):
        pass