# pyright: reportMissingImports=false
# app/ui/color_wheel.py
from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageTk


class ColorWheelWidget(tk.Canvas):
    """
    HSV colour wheel rendered via Pillow.

    - Centre = white (S=0), edge = fully saturated (S=1).
    - Value (brightness) is always 1.0 on the wheel itself; the separate
      Brightness slider multiplies only the BLE output.
    - Draggable white cursor dot marks the current hue/saturation position.

    Public API
    ----------
    set_rgb(r, g, b) — move cursor to match the RGB value (no callback fired).
    on_change        — callable(r, g, b) assigned after construction.
    """

    CURSOR_RADIUS = 7
    CURSOR_OUTLINE = "#ffffff"
    CURSOR_FILL = "#333333"

    def __init__(
        self,
        parent: Any,
        size: int = 200,
        bg: str = "#242424",
        on_change: Callable[[int, int, int], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            cursor="crosshair",
            **kwargs,
        )
        self._size = size
        self._radius = (size - 2) // 2  # slight inset so edge pixels are clean
        self._cx = size // 2
        self._cy = size // 2
        self.on_change = on_change

        # Current hue/saturation (V is always 1 on wheel)
        self._hue: float = 0.0  # 0–360
        self._sat: float = 1.0  # 0–1

        self._photo: ImageTk.PhotoImage | None = None
        self._cursor_id: int = 0
        self._dragging: bool = False

        self._render_wheel()
        self._draw_cursor()

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ──────────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────────

    def set_rgb(self, r: int, g: int, b: int) -> None:
        """Move cursor to match RGB without firing on_change callback."""
        h, s, _v = _rgb_to_hsv(r, g, b)
        self._hue = h
        self._sat = s
        self._draw_cursor()

    # ──────────────────────────────────────────────────────────────────────
    # Rendering
    # ──────────────────────────────────────────────────────────────────────

    def _render_wheel(self) -> None:
        """Build the colour wheel image using Pillow and cache it on the Canvas."""
        size = self._size
        cx = cy = size / 2
        r_max = self._radius

        bg_color: tuple[int, int, int] = (36, 36, 36)  # matches canvas bg
        img = Image.new("RGB", (size, size), bg_color)
        pixels = img.load()
        assert pixels is not None

        for py in range(size):
            for px in range(size):
                dx = px - cx
                dy = py - cy
                dist = math.hypot(dx, dy)
                if dist > r_max:
                    continue  # outside circle — keep bg colour

                # Polar → hue (angle) + saturation (radius fraction)
                angle = math.degrees(math.atan2(-dy, dx)) % 360
                sat = dist / r_max

                rgb = _hsv_to_rgb(angle, sat, 1.0)
                pixels[px, py] = rgb  # type: ignore[index]

        self._photo = ImageTk.PhotoImage(img)
        self.create_image(0, 0, anchor="nw", image=self._photo, tags="wheel")

    def _draw_cursor(self) -> None:
        """Redraw the cursor dot at the current hue/saturation position."""
        if self._cursor_id:
            self.delete(self._cursor_id)

        x, y = self._hs_to_xy(self._hue, self._sat)
        r = self.CURSOR_RADIUS
        self._cursor_id = self.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            outline=self.CURSOR_OUTLINE,
            fill=self.CURSOR_FILL,
            width=2,
            tags="cursor",
        )
        # Cursor always on top
        self.tag_raise("cursor")

    # ──────────────────────────────────────────────────────────────────────
    # Coordinate helpers
    # ──────────────────────────────────────────────────────────────────────

    def _hs_to_xy(self, hue: float, sat: float) -> tuple[float, float]:
        angle_rad = math.radians(hue)
        dist = sat * self._radius
        x = self._cx + dist * math.cos(angle_rad)
        y = self._cy - dist * math.sin(angle_rad)
        return x, y

    def _xy_to_hs(self, x: float, y: float) -> tuple[float, float]:
        dx = x - self._cx
        dy = y - self._cy
        dist = math.hypot(dx, dy)
        sat = min(dist / self._radius, 1.0)
        hue = math.degrees(math.atan2(-dy, dx)) % 360
        return hue, sat

    # ──────────────────────────────────────────────────────────────────────
    # Mouse events
    # ──────────────────────────────────────────────────────────────────────

    def _on_press(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._dragging = True
        self._update_from_xy(event.x, event.y)

    def _on_drag(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self._dragging:
            self._update_from_xy(event.x, event.y)

    def _on_release(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._dragging = False

    def _update_from_xy(self, x: float, y: float) -> None:
        hue, sat = self._xy_to_hs(x, y)
        self._hue = hue
        self._sat = sat
        self._draw_cursor()
        if self.on_change:
            r, g, b = _hsv_to_rgb(hue, sat, 1.0)
            self.on_change(r, g, b)


# ──────────────────────────────────────────────────────────────────────────────
# Colour math helpers
# ──────────────────────────────────────────────────────────────────────────────


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """h: 0–360, s: 0–1, v: 0–1  →  r, g, b: 0–255"""
    if s == 0.0:
        val = int(round(v * 255))
        return val, val, val
    h /= 60.0
    i = int(h)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    table = [
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    ]
    r, g, b = table[i % 6]
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """r, g, b: 0–255  →  h: 0–360, s: 0–1, v: 0–1"""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    v = cmax
    s = 0.0 if cmax == 0 else delta / cmax

    if delta == 0:
        h = 0.0
    elif cmax == rf:
        h = 60.0 * (((gf - bf) / delta) % 6)
    elif cmax == gf:
        h = 60.0 * (((bf - rf) / delta) + 2)
    else:
        h = 60.0 * (((rf - gf) / delta) + 4)

    return h % 360, s, v
