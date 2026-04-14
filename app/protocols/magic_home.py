# app/protocols/magic_home.py
#
# Совместимый слой поверх app.ble.protocol.
# Старые имена (color_command / power_command / effect_command) переэкспортируются
# так, что существующие вызовы в UI и тестах продолжают работать без изменений.
from __future__ import annotations

from app.ble.protocol import (
    cmd_color,
    cmd_effect,
    cmd_power_off,
    cmd_power_on,
)


def clamp_byte(value: int) -> int:
    return max(0, min(255, int(value)))


def color_command(r: int, g: int, b: int) -> bytes:
    return cmd_color(r, g, b)


def power_command(is_on: bool) -> bytes:
    return cmd_power_on() if is_on else cmd_power_off()


def effect_command(effect_code: int, speed: int) -> bytes:
    return cmd_effect(effect_code, speed)
