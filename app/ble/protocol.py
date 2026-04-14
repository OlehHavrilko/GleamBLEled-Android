# pyright: reportMissingImports=false
# app/ble/protocol.py
#
# Авторитетный модуль протокола для контроллера ELK-BLEDOM (и совместимых).
# Все константы получены из прямого анализа GATT-сервисов устройства.
# Не импортирует ничего из пакета app/ — намеренно изолирован.
from __future__ import annotations

# ── Идентификаторы устройства ─────────────────────────────────────────────────
DEVICE_NAME = "ELK-BLEDOM"
DEVICE_MAC = "FF:FF:10:69:5B:2A"

# ── UUID GATT ──────────────────────────────────────────────────────────────────
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"

# Второй сервис — предположительно OTA/прошивка, не трогаем для записи LED.
OTA_SERVICE_UUID = "5833ff01-9b21-4c01-8e52-c2a9106a8ef6"
OTA_WRITE_UUID = "5833ff02-9b21-4c01-8e52-c2a9106a8ef6"

# ── MTU ───────────────────────────────────────────────────────────────────────
DEVICE_MTU = 247  # байт — подтверждено из характеристик устройства


# ── Команды (все кадры 9 байт: 7E ... EF) ─────────────────────────────────────


def _clamp(value: int) -> int:
    return max(0, min(255, int(value)))


def cmd_color(r: int, g: int, b: int) -> bytes:
    """Установить цвет RGB. Кадр: 7E 00 05 03 RR GG BB 00 EF."""
    return bytes([0x7E, 0x00, 0x05, 0x03, _clamp(r), _clamp(g), _clamp(b), 0x00, 0xEF])


def cmd_power_on() -> bytes:
    """Включить светодиоды. Кадр: 7E 00 04 F0 00 01 FF 00 EF."""
    return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])


def cmd_power_off() -> bytes:
    """Выключить светодиоды. Кадр: 7E 00 04 F0 00 00 FF 00 EF."""
    return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x00, 0xFF, 0x00, 0xEF])


def cmd_effect(effect_code: int, speed: int) -> bytes:
    """Встроенный эффект. Кадр: 7E 00 03 CC SS 00 EF (7 байт)."""
    return bytes([0x7E, 0x00, 0x03, _clamp(effect_code), _clamp(speed), 0x00, 0xEF])


# ── Парсинг уведомления состояния ─────────────────────────────────────────────


def parse_state(raw: bytes) -> dict[str, int]:
    """
    Разобрать notify-уведомление состояния.

    Формат ответа: 7E-07-05-03-RR-GG-BB-00-EF (9 байт).
    Возвращает {"r": int, "g": int, "b": int} или {} при ошибке парсинга.
    """
    if len(raw) == 9 and raw[0] == 0x7E and raw[-1] == 0xEF:
        return {"r": raw[4], "g": raw[5], "b": raw[6]}
    return {}
