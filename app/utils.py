from __future__ import annotations


def hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    raw = color_hex.strip().lstrip("#")
    if len(raw) != 6:
        raise ValueError("HEX color must contain exactly 6 hex digits")

    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return (
        f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"
    )


def apply_brightness(
    r: int, g: int, b: int, brightness: float | int
) -> tuple[int, int, int]:
    if isinstance(brightness, int):
        factor = max(0, min(100, brightness)) / 100.0
    else:
        factor = max(0.0, min(1.0, brightness))
    return int(r * factor), int(g * factor), int(b * factor)


def rssi_to_bars(rssi: int | None) -> str:
    if rssi is None:
        return "░░░░"
    if rssi >= -50:
        return "████"
    if rssi >= -65:
        return "███░"
    if rssi >= -75:
        return "██░░"
    return "█░░░"
