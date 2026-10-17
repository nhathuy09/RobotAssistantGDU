import pygame

class AppManager:
    def __init__(self):
        self.current_app = None
        self.apps = {}

    def register_app(self, name: str, app):
        self.apps[name] = app

    def switch_app(self, name: str):
        if name in self.apps:
            if self.current_app is not None:
                self.current_app.on_exit()
            self.current_app = self.apps[name]
            self.current_app.on_enter()