# pyright: reportMissingImports=false
# app/ui/widgets.py
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any


class GradientSlider(tk.Canvas):
    """
    Horizontal slider with a gradient track (black → colour) and a white thumb.

    Performance note: the gradient is drawn once on creation / colour change;
    only the thumb oval is redrawn on every value change.

    Parameters
    ----------
    from_ / to      — value range (default 0–255)
    color           — right-side (maximum) track colour, e.g. "#ff0000"
    value           — initial value
    command         — callable(value: int) called on every change
    """

    TRACK_HEIGHT = 8
    THUMB_RADIUS = 9
    THUMB_FILL = "#e8e8e8"
    THUMB_OUTLINE = "#888888"

    def __init__(
        self,
        parent: Any,
        width: int = 200,
        from_: int = 0,
        to: int = 255,
        color: str = "#ffffff",
        value: int = 0,
        command: Callable[[int], None] | None = None,
        bg: str = "#242424",
        **kwargs: Any,
    ) -> None:
        height = self.THUMB_RADIUS * 2 + 4
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self._width = width
        self._height = height
        self._from = from_
        self._to = to
        self._color = color
        self._value = max(from_, min(to, value))
        self.command = command

        self._track_id: int = 0
        self._thumb_id: int = 0

        self._render_track()
        self._render_thumb()

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ──────────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────────

    def get(self) -> int:
        return self._value

    def set(self, value: int) -> None:
        self._value = max(self._from, min(self._to, int(round(value))))
        self._render_thumb()

    def set_color(self, color: str) -> None:
        """Update the gradient end colour (e.g. when RGB channel value changes)."""
        self._color = color
        self._render_track()
        self._render_thumb()

    # ──────────────────────────────────────────────────────────────────────
    # Rendering
    # ──────────────────────────────────────────────────────────────────────

    def _track_x_range(self) -> tuple[int, int]:
        pad = self.THUMB_RADIUS
        return pad, self._width - pad

    def _render_track(self) -> None:
        """Draw the gradient track as individual 1-px-wide vertical stripes."""
        x0, x1 = self._track_x_range()
        cy = self._height // 2
        th = self.TRACK_HEIGHT
        y0 = cy - th // 2
        y1 = cy + th // 2

        # Parse the target colour
        r2, g2, b2 = _hex_to_rgb(self._color)

        self.delete("track")
        track_w = max(x1 - x0, 1)
        for i in range(track_w):
            t = i / track_w
            r = int(r2 * t)
            g = int(g2 * t)
            b = int(b2 * t)
            px = x0 + i
            self.create_line(
                px,
                y0,
                px,
                y1,
                fill=f"#{r:02x}{g:02x}{b:02x}",
                tags="track",
            )
        # Rounded-cap look: draw a rectangle background first, clip with ovals
        # For simplicity we just draw the stripes — good enough at this size.

    def _render_thumb(self) -> None:
        """Move/redraw just the thumb oval."""
        if self._thumb_id:
            self.delete(self._thumb_id)

        x = self._value_to_x(self._value)
        cy = self._height // 2
        r = self.THUMB_RADIUS
        self._thumb_id = self.create_oval(
            x - r,
            cy - r,
            x + r,
            cy + r,
            fill=self.THUMB_FILL,
            outline=self.THUMB_OUTLINE,
            width=1.5,
            tags="thumb",
        )
        self.tag_raise("thumb")

    # ──────────────────────────────────────────────────────────────────────
    # Coordinate helpers
    # ──────────────────────────────────────────────────────────────────────

    def _value_to_x(self, value: int) -> int:
        x0, x1 = self._track_x_range()
        t = (value - self._from) / max(self._to - self._from, 1)
        return int(x0 + t * (x1 - x0))

    def _x_to_value(self, x: int) -> int:
        x0, x1 = self._track_x_range()
        t = (x - x0) / max(x1 - x0, 1)
        t = max(0.0, min(1.0, t))
        return int(round(self._from + t * (self._to - self._from)))

    # ──────────────────────────────────────────────────────────────────────
    # Mouse events
    # ──────────────────────────────────────────────────────────────────────

    def _on_press(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._update_from_x(event.x)

    def _on_drag(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._update_from_x(event.x)

    def _on_release(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        pass

    def _update_from_x(self, x: int) -> None:
        new_val = self._x_to_value(x)
        if new_val != self._value:
            self._value = new_val
            self._render_thumb()
            if self.command:
                self.command(new_val)


# ──────────────────────────────────────────────────────────────────────────────


class ColorSwatch(tk.Canvas):
    """
    Circular colour preset button.

    Active state shows a white ring border.
    Clicking fires the `on_click(r, g, b)` callback.
    """

    BORDER_ACTIVE = "#ffffff"
    BORDER_INACTIVE = "#444444"
    BORDER_WIDTH = 2
    ACTIVE_BORDER_WIDTH = 3

    def __init__(
        self,
        parent: Any,
        r: int,
        g: int,
        b: int,
        size: int = 32,
        on_click: Callable[[int, int, int], None] | None = None,
        bg: str = "#242424",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self._r = r
        self._g = g
        self._b = b
        self._size = size
        self._active = False
        self.on_click = on_click

        self._draw()
        self.bind("<ButtonPress-1>", self._on_press)

    # ──────────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────────

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self._draw()

    # ──────────────────────────────────────────────────────────────────────
    # Rendering
    # ──────────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.delete("all")
        s = self._size
        pad = 2
        color_hex = f"#{self._r:02x}{self._g:02x}{self._b:02x}"

        if self._active:
            outline = self.BORDER_ACTIVE
            bw = self.ACTIVE_BORDER_WIDTH
        else:
            outline = self.BORDER_INACTIVE
            bw = self.BORDER_WIDTH

        self.create_oval(
            pad,
            pad,
            s - pad,
            s - pad,
            fill=color_hex,
            outline=outline,
            width=bw,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Mouse
    # ──────────────────────────────────────────────────────────────────────

    def _on_press(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self.on_click:
            self.on_click(self._r, self._g, self._b)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return 255, 255, 255
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
