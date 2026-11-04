
from functools import lru_cache
from pathlib import Path

import pygame

ICON_DIR = Path(__file__).resolve().parent / "assets" / "icon"


@lru_cache(maxsize=32)
def _source(name):
    source = pygame.image.load(str(ICON_DIR / f"{name}.png"))
    bounds = source.get_bounding_rect(min_alpha=1)
    return source.subsurface(bounds).copy() if bounds.width and bounds.height else source


@lru_cache(maxsize=128)
def get_icon(name, size, color=None):
    source = _source(name)
    width, height = source.get_size()
    ratio = size / max(width, height)
    icon = pygame.transform.smoothscale(source, (max(1, round(width * ratio)), max(1, round(height * ratio))))
    if color is not None:
        icon.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        icon.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return icon


def draw_icon(surface, name, center, size, color=None):
    icon = get_icon(name, size, tuple(color) if color is not None else None)
    surface.blit(icon, icon.get_rect(center=center))
