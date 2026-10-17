import pygame
from typing import Optional, Tuple
from display.components.assistive_touch import AssistiveTouch
pygame.init()
screen = pygame.display.set_mode((800, 480))
assistive_touch = AssistiveTouch(screen_size=(800, 480))
running = True
clock = pygame.time.Clock()
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        assistive_touch.handle_event(event)

    assistive_touch.update()

    screen.fill((205, 214, 224))
    assistive_touch.draw(screen)
    pygame.display.flip()
    clock.tick(30)

pygame.quit()