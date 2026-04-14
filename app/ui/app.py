# pyright: reportMissingImports=false
# app/ui/app.py
from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from typing import Any

import customtkinter as ctk

from app.ble.async_runner import AsyncioThread
from app.ble.controller import BleLedController
from app.ble.protocol import WRITE_UUID as DEFAULT_WRITE_UUID
from app.ble.scanner import GleamScanner, ProbeCandidate
from app.config import ConfigStore
from app.constants import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_EFFECT_SPEED,
    DEEP_SCAN_SECONDS,
    LAST_DEVICE_CONNECT_TIMEOUT,
    QUICK_SCAN_SECONDS,
    RECONNECT_INTERVAL_SECONDS,
    RECONNECT_MAX_ATTEMPTS,
)
from app.models import AppState, DeviceInfo
from app.protocols.magic_home import color_command, effect_command, power_command
from app.utils import apply_brightness, hex_to_rgb, rgb_to_hex, rssi_to_bars
from app.ble.protocol import parse_state
from app.ui.device_picker import DevicePickerDialog
from app.ui.color_wheel import ColorWheelWidget
from app.ui.widgets import ColorSwatch, GradientSlider


# ── Palette ───────────────────────────────────────────────────────────────────
_BG_OUTER = "#1a1a1a"
_BG_PANEL = "#242424"
_TEXT = "#e8e8e8"
_MUTED = "#888888"
_ACCENT = "#3d7ef5"
_DOT_GREEN = "#2f9e44"
_DOT_YELLOW = "#f59f00"
_DOT_RED = "#c92a2a"

# ── Effects map ───────────────────────────────────────────────────────────────
_EFFECTS: dict[str, int | None] = {
    "Breathe": 0x25,
    "Cycle": 0x26,
    "Strobe": 0x27,
    "Flash": 0x38,
}

# ── Colour presets (name, R, G, B) ────────────────────────────────────────────
_PRESETS: list[tuple[str, int, int, int]] = [
    ("White", 255, 255, 255),
    ("Red", 255, 0, 0),
    ("Green", 0, 200, 0),
    ("Blue", 0, 0, 255),
    ("Cyan", 0, 220, 220),
    ("Magenta", 220, 0, 220),
    ("Orange", 255, 100, 0),
    ("Yellow", 255, 220, 0),
]

_WHEEL_SIZE = 200
_WIN_W = 380
_WIN_H = 640


class LedApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Gleam")
        self.geometry(f"{_WIN_W}x{_WIN_H}")
        self.resizable(False, False)
        self.configure(bg=_BG_OUTER)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._config = ConfigStore(_default_config_path())
        self._state: AppState = self._config.load()
        self._loop = AsyncioThread()
        self._scanner = GleamScanner()
        self._controller = BleLedController(on_disconnect=self._on_device_disconnected)

        # ── UI state ──────────────────────────────────────────────────────
        self._known_devices: dict[str, DeviceInfo] = {}
        self._connected_device: DeviceInfo | None = None

        self._status_text = tk.StringVar(value="Инициализация…")
        self._hex_var = tk.StringVar(value=self._state.color_hex)

        # Prevent feedback loops between wheel ↔ sliders ↔ hex
        self._syncing = False

        self._debounce_job: str | None = None
        self._reconnect_attempts = 0
        self._reconnect_job: str | None = None

        # Active effect button reference
        self._active_effect: str | None = None

        self._build_ui()
        self._set_color_from_hex(self._state.color_hex, send=False)

        self.after(200, self._startup_autoconnect)

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Root uses simple pack layout top-to-bottom
        self._build_header()
        self._build_device_bar()
        self._build_wheel_section()
        self._build_hex_row()
        self._build_sliders_section()
        self._build_presets_section()
        self._build_effects_section()
        self._build_status_bar()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Header (44 px) ────────────────────────────────────────────────────

    def _build_header(self) -> None:
        bar = tk.Frame(self, bg=_BG_PANEL, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar,
            text="Gleam",
            bg=_BG_PANEL,
            fg=_MUTED,
            font=("Helvetica", 15, "bold"),
        ).pack(side="left", padx=16, pady=10)

        # Power switch (ON/OFF) on the right
        self._power_switch = ctk.CTkSwitch(
            bar,
            text="",
            width=46,
            command=self._on_power_switch,
            onvalue=True,
            offvalue=False,
            fg_color=_DOT_RED,
            progress_color=_DOT_GREEN,
        )
        self._power_switch.pack(side="right", padx=16, pady=10)
        if self._state.power_on:
            self._power_switch.select()
        else:
            self._power_switch.deselect()

    # ── Device bar (40 px) ────────────────────────────────────────────────

    def _build_device_bar(self) -> None:
        bar = tk.Frame(self, bg=_BG_PANEL, height=40)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # BLE status dot
        self._ble_dot = tk.Label(
            bar,
            text="●",
            bg=_BG_PANEL,
            fg=_DOT_RED,
            font=("Helvetica", 12),
        )
        self._ble_dot.pack(side="left", padx=(10, 4), pady=10)

        # Device name label (expands)
        self._device_label = tk.Label(
            bar,
            text="Not connected",
            bg=_BG_PANEL,
            fg=_TEXT,
            font=("Helvetica", 11),
            anchor="w",
        )
        self._device_label.pack(side="left", fill="x", expand=True, pady=10)

        # [Scan] button
        ctk.CTkButton(
            bar,
            text="Scan",
            width=60,
            height=26,
            fg_color=_BG_OUTER,
            hover_color="#2a2a2a",
            border_width=1,
            border_color=_MUTED,
            text_color=_TEXT,
            font=ctk.CTkFont(size=11),
            command=self._scan_quick,
        ).pack(side="right", padx=(4, 10), pady=7)

        # [×] disconnect
        self._disco_btn = ctk.CTkButton(
            bar,
            text="×",
            width=28,
            height=26,
            fg_color=_BG_OUTER,
            hover_color="#3a1010",
            border_width=1,
            border_color=_MUTED,
            text_color=_MUTED,
            font=ctk.CTkFont(size=14),
            command=self._disconnect,
        )
        self._disco_btn.pack(side="right", padx=(0, 4), pady=7)

    # ── Colour wheel ──────────────────────────────────────────────────────

    def _build_wheel_section(self) -> None:
        frame = tk.Frame(self, bg=_BG_OUTER)
        frame.pack(fill="x", pady=(12, 0))

        self._wheel = ColorWheelWidget(
            frame,
            size=_WHEEL_SIZE,
            bg=_BG_OUTER,
            on_change=self._on_wheel_change,
        )
        self._wheel.pack(anchor="center")

    # ── Hex + preview ─────────────────────────────────────────────────────

    def _build_hex_row(self) -> None:
        frame = tk.Frame(self, bg=_BG_OUTER)
        frame.pack(fill="x", padx=20, pady=(8, 0))

        # Colour preview square
        self._preview_swatch = tk.Frame(
            frame,
            bg=self._state.color_hex,
            width=28,
            height=28,
        )
        self._preview_swatch.pack(side="left", padx=(0, 8))
        self._preview_swatch.pack_propagate(False)

        # Hex entry
        self._hex_entry = ctk.CTkEntry(
            frame,
            textvariable=self._hex_var,
            width=110,
            height=28,
            font=ctk.CTkFont(size=12, family="Courier"),
            fg_color=_BG_PANEL,
            text_color=_TEXT,
            border_color=_MUTED,
        )
        self._hex_entry.pack(side="left")
        self._hex_entry.bind("<Return>", lambda _e: self._apply_hex_entry())

    # ── RGB + Brightness sliders ──────────────────────────────────────────

    def _build_sliders_section(self) -> None:
        frame = tk.Frame(self, bg=_BG_OUTER)
        frame.pack(fill="x", padx=20, pady=(10, 0))

        try:
            r, g, b = hex_to_rgb(self._state.color_hex)
        except ValueError:
            r, g, b = 255, 102, 0

        slider_w = _WIN_W - 20 - 20 - 30 - 8  # total - padx*2 - label - value_label

        self._r_slider = self._make_slider(
            frame,
            0,
            "R",
            "#ff0000",
            r,
            slider_w,
            lambda v: self._on_rgb_slider("r", v),
        )
        self._g_slider = self._make_slider(
            frame,
            1,
            "G",
            "#00cc00",
            g,
            slider_w,
            lambda v: self._on_rgb_slider("g", v),
        )
        self._b_slider = self._make_slider(
            frame,
            2,
            "B",
            "#0055ff",
            b,
            slider_w,
            lambda v: self._on_rgb_slider("b", v),
        )

        # Brightness row
        row = tk.Frame(frame, bg=_BG_OUTER)
        row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        tk.Label(
            row, text="✦", bg=_BG_OUTER, fg=_MUTED, font=("Helvetica", 12), width=3
        ).pack(side="left")
        self._bright_slider = GradientSlider(
            row,
            width=slider_w,
            from_=0,
            to=100,
            color="#ffffff",
            value=int(self._state.brightness * 100),
            command=self._on_brightness,
            bg=_BG_OUTER,
        )
        self._bright_slider.pack(side="left")
        self._bright_val = tk.Label(
            row,
            text=f"{int(self._state.brightness * 100)}",
            bg=_BG_OUTER,
            fg=_MUTED,
            font=("Helvetica", 10),
            width=4,
            anchor="e",
        )
        self._bright_val.pack(side="left")

    def _make_slider(
        self,
        parent: tk.Frame,
        row: int,
        label: str,
        color: str,
        init_value: int,
        width: int,
        command: Callable[[int], None],
    ) -> GradientSlider:
        frame = tk.Frame(parent, bg=_BG_OUTER)
        frame.grid(row=row, column=0, sticky="ew", pady=2)

        tk.Label(
            frame, text=label, bg=_BG_OUTER, fg=_MUTED, font=("Helvetica", 11), width=3
        ).pack(side="left")

        slider = GradientSlider(
            frame,
            width=width,
            from_=0,
            to=255,
            color=color,
            value=init_value,
            command=command,
            bg=_BG_OUTER,
        )
        slider.pack(side="left")

        val_label = tk.Label(
            frame,
            text=str(init_value),
            bg=_BG_OUTER,
            fg=_MUTED,
            font=("Helvetica", 10),
            width=4,
            anchor="e",
        )
        val_label.pack(side="left")

        # Store value label reference on the slider for updates
        slider._val_label = val_label  # type: ignore[attr-defined]
        return slider

    # ── Colour presets ────────────────────────────────────────────────────

    def _build_presets_section(self) -> None:
        frame = tk.Frame(self, bg=_BG_OUTER)
        frame.pack(fill="x", padx=20, pady=(12, 0))

        self._swatches: list[ColorSwatch] = []
        for i, (name, r, g, b) in enumerate(_PRESETS):
            swatch = ColorSwatch(
                frame,
                r=r,
                g=g,
                b=b,
                size=32,
                bg=_BG_OUTER,
                on_click=self._on_preset_click,
            )
            swatch.grid(row=0, column=i, padx=3)
            self._swatches.append(swatch)

    # ── Effects panel ─────────────────────────────────────────────────────

    def _build_effects_section(self) -> None:
        outer = tk.Frame(self, bg=_BG_PANEL)
        outer.pack(fill="x", padx=12, pady=(12, 0))

        btn_frame = tk.Frame(outer, bg=_BG_PANEL)
        btn_frame.pack(fill="x", padx=8, pady=(8, 4))

        self._effect_btns: dict[str, ctk.CTkButton] = {}

        for name in _EFFECTS:
            btn = ctk.CTkButton(
                btn_frame,
                text=name,
                width=62,
                height=28,
                fg_color=_BG_OUTER,
                hover_color="#2d2d2d",
                border_width=1,
                border_color=_MUTED,
                text_color=_TEXT,
                font=ctk.CTkFont(size=11),
                command=lambda n=name: self._on_effect_btn(n),
            )
            btn.pack(side="left", padx=2)
            self._effect_btns[name] = btn

        # Stop button
        stop_btn = ctk.CTkButton(
            btn_frame,
            text="■ Stop",
            width=62,
            height=28,
            fg_color=_BG_OUTER,
            hover_color="#3a1010",
            border_width=1,
            border_color=_MUTED,
            text_color=_MUTED,
            font=ctk.CTkFont(size=11),
            command=self._stop_effect,
        )
        stop_btn.pack(side="left", padx=2)
        self._stop_btn = stop_btn

        # Speed slider
        speed_frame = tk.Frame(outer, bg=_BG_PANEL)
        speed_frame.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(
            speed_frame, text="Speed", bg=_BG_PANEL, fg=_MUTED, font=("Helvetica", 10)
        ).pack(side="left", padx=(0, 6))
        self._speed_slider = GradientSlider(
            speed_frame,
            width=_WIN_W - 12 * 2 - 8 * 2 - 50 - 8,
            from_=1,
            to=255,
            color="#aaaaaa",
            value=DEFAULT_EFFECT_SPEED,
            bg=_BG_PANEL,
        )
        self._speed_slider.pack(side="left")

    # ── Status bar (26 px) ────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bg=_BG_PANEL, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._status_label = tk.Label(
            bar,
            textvariable=self._status_text,
            bg=_BG_PANEL,
            fg=_MUTED,
            font=("Helvetica", 10),
            anchor="w",
        )
        self._status_label.pack(fill="x", padx=10, pady=4)

    # ──────────────────────────────────────────────────────────────────────
    # Startup / scan / connect
    # ──────────────────────────────────────────────────────────────────────

    def _startup_autoconnect(self) -> None:
        last = self._state.last_device
        if last:
            self._set_status(f"Connecting to {last.name}…")
            self._set_dot(_DOT_YELLOW)
            self._device_label.config(text=f"Connecting to {last.name}…")

            def on_success(_: Any) -> None:
                device = DeviceInfo(
                    name=last.name,
                    address=last.address,
                    write_uuid=last.write_uuid,
                    confidence=last.confidence,
                )
                self._on_connected(device)

            def on_error(_exc: Exception) -> None:
                self._set_status("Last device unavailable — scanning…")
                self._scan_quick()

            self._run_async(
                self._controller.connect(
                    last.address,
                    timeout=LAST_DEVICE_CONNECT_TIMEOUT,
                    preferred_write_uuid=last.write_uuid,
                ),
                on_success=on_success,
                on_error=on_error,
            )
        else:
            self._scan_quick()

    def _scan_quick(self) -> None:
        self._set_status(f"Scanning ({int(QUICK_SCAN_SECONDS)} s)…")
        self._set_dot(_DOT_YELLOW)
        self._device_label.config(text="Scanning…")
        self._run_async(
            self._scanner.scan(duration=QUICK_SCAN_SECONDS),
            on_success=self._on_scan_result,
        )

    def _on_scan_result(
        self, result: tuple[list[DeviceInfo], list[ProbeCandidate]]
    ) -> None:
        devices, _unknowns = result
        self._known_devices = {d.address: d for d in devices}

        if len(devices) == 1:
            self._set_status(f"Found: {devices[0].name} — connecting…")
            self._connect_device(devices[0])
        elif len(devices) > 1:
            self._set_status(f"Found {len(devices)} devices.")
            self._set_dot(_DOT_RED)
            self._show_picker(devices, [])
        else:
            self._set_status("No devices found.")
            self._set_dot(_DOT_RED)
            self._device_label.config(text="Not connected")

    def _show_picker(
        self,
        devices: list[DeviceInfo],
        unknowns: list[ProbeCandidate],
    ) -> None:
        DevicePickerDialog(
            parent=self,
            devices=devices,
            unknowns=unknowns,
            on_connect=self._connect_device,
            on_probe=self._probe_candidate,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Connect / disconnect
    # ──────────────────────────────────────────────────────────────────────

    def _connect_device(self, device: DeviceInfo) -> None:
        self._set_status(f"Connecting to {device.name}…")
        self._set_dot(_DOT_YELLOW)
        self._device_label.config(text=f"{device.name}…")

        ble_device = self._scanner.get_ble_device(device.address)

        def on_success(_: Any) -> None:
            self._on_connected(device)

        self._run_async(
            self._controller.connect(
                device.address,
                timeout=DEFAULT_CONNECT_TIMEOUT,
                preferred_write_uuid=device.write_uuid or DEFAULT_WRITE_UUID,
                ble_device=ble_device,
            ),
            on_success=on_success,
        )

    def _on_connected(self, device: DeviceInfo) -> None:
        self._reconnect_attempts = 0
        self._cancel_reconnect()

        if self._controller.write_uuid:
            device = DeviceInfo(
                name=device.name,
                address=device.address,
                rssi=device.rssi,
                confidence=device.confidence,
                write_uuid=self._controller.write_uuid,
            )

        self._connected_device = device
        self._state.remember_device(device)
        self._save_state()

        bars = rssi_to_bars(device.rssi)
        rssi_str = f" {device.rssi} dBm" if device.rssi else ""
        self._device_label.config(text=f"{device.name}  {bars}{rssi_str}")
        self._set_dot(_DOT_GREEN)
        self._set_status(f"Connected: {device.name}")

        self._run_async(
            self._controller.subscribe_notify(self._on_notify_raw),
            on_success=lambda ok: self._set_status(
                f"Connected: {device.name}" + ("  [notify ✓]" if ok else "")
            ),
        )
        self._send_color_debounced()

    def _probe_candidate(self, candidate: ProbeCandidate) -> None:
        self._set_status(f"Probing {candidate.name}…")
        self._set_dot(_DOT_YELLOW)

        def on_success(confirmed: DeviceInfo | None) -> None:
            if confirmed:
                self._connect_device(confirmed)
            else:
                self._set_status(f"✗ {candidate.name} not confirmed as LED controller")
                self._set_dot(_DOT_RED)

        self._run_async(self._scanner.probe_unknown(candidate), on_success=on_success)

    def _disconnect(self) -> None:
        self._cancel_reconnect()
        self._run_async(
            self._controller.disconnect(),
            on_success=lambda _: self._on_disconnected_clean(),
        )

    def _on_disconnected_clean(self) -> None:
        self._connected_device = None
        self._set_dot(_DOT_RED)
        self._device_label.config(text="Not connected")
        self._set_status("Disconnected")

    # ──────────────────────────────────────────────────────────────────────
    # Background reconnect
    # ──────────────────────────────────────────────────────────────────────

    def _on_device_disconnected(self) -> None:
        self.after(0, self._handle_unexpected_disconnect)

    def _handle_unexpected_disconnect(self) -> None:
        self._connected_device = None
        self._set_dot(_DOT_YELLOW)
        self._device_label.config(text="Reconnecting…")
        self._set_status("Connection lost. Reconnecting…")
        self._reconnect_attempts = 0
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        self._reconnect_job = self.after(
            int(RECONNECT_INTERVAL_SECONDS * 1000), self._try_reconnect
        )

    def _try_reconnect(self) -> None:
        self._reconnect_job = None
        last = self._state.last_device
        if not last:
            self._set_dot(_DOT_RED)
            self._set_status("No saved device for reconnect.")
            return

        self._reconnect_attempts += 1
        self._set_status(
            f"Reconnecting to {last.name} "
            f"({self._reconnect_attempts}/{RECONNECT_MAX_ATTEMPTS})…"
        )

        def on_success(_: Any) -> None:
            device = DeviceInfo(
                name=last.name,
                address=last.address,
                write_uuid=last.write_uuid,
                confidence=last.confidence,
            )
            self._on_connected(device)

        def on_error(_exc: Exception) -> None:
            if self._reconnect_attempts < RECONNECT_MAX_ATTEMPTS:
                self._schedule_reconnect()
            else:
                self._set_dot(_DOT_RED)
                self._device_label.config(text="Device lost")
                self._set_status(
                    f"Failed to reconnect after {RECONNECT_MAX_ATTEMPTS} attempts."
                )

        self._run_async(
            self._controller.connect(
                last.address,
                timeout=LAST_DEVICE_CONNECT_TIMEOUT,
                preferred_write_uuid=last.write_uuid,
            ),
            on_success=on_success,
            on_error=on_error,
        )

    def _cancel_reconnect(self) -> None:
        if self._reconnect_job:
            self.after_cancel(self._reconnect_job)
            self._reconnect_job = None
        self._reconnect_attempts = 0

    # ──────────────────────────────────────────────────────────────────────
    # Colour control — callbacks
    # ──────────────────────────────────────────────────────────────────────

    def _on_wheel_change(self, r: int, g: int, b: int) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._apply_rgb(r, g, b)
        finally:
            self._syncing = False
        self._send_color_debounced()

    def _on_rgb_slider(self, channel: str, value: int) -> None:
        if self._syncing:
            return
        r = self._r_slider.get()
        g = self._g_slider.get()
        b = self._b_slider.get()

        # Update the corresponding slider value label
        slider_map = {"r": self._r_slider, "g": self._g_slider, "b": self._b_slider}
        sl = slider_map[channel]
        if hasattr(sl, "_val_label"):
            sl._val_label.config(text=str(value))  # type: ignore[attr-defined]

        # Update gradient colour of each channel slider to reflect current mix
        self._r_slider.set_color(f"#{r:02x}0000")
        self._g_slider.set_color(f"#00{g:02x}00")
        self._b_slider.set_color(f"#0000{b:02x}")

        color_hex = rgb_to_hex(r, g, b)
        self._syncing = True
        try:
            self._hex_var.set(color_hex)
            self._preview_swatch.config(bg=color_hex)
            self._wheel.set_rgb(r, g, b)
            self._state.color_hex = color_hex
            self._save_state()
            self._update_active_swatch(r, g, b)
        finally:
            self._syncing = False
        self._send_color_debounced()

    def _on_brightness(self, value: int) -> None:
        self._state.brightness = value / 100.0
        self._bright_val.config(text=str(value))
        self._save_state()
        self._send_color_debounced()

    def _apply_hex_entry(self) -> None:
        try:
            r, g, b = hex_to_rgb(self._hex_var.get())
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._set_color_from_rgb(r, g, b)
        self._send_color_debounced()

    def _on_preset_click(self, r: int, g: int, b: int) -> None:
        self._set_color_from_rgb(r, g, b)
        self._send_color_debounced()

    def _on_power_switch(self) -> None:
        is_on: bool = self._power_switch.get()
        self._state.power_on = is_on
        self._save_state()
        self._run_async(
            self._controller.send(power_command(is_on)),
            on_success=lambda _: self._set_status("Power ON" if is_on else "Power OFF"),
        )

    # ── Effects ──────────────────────────────────────────────────────────

    def _on_effect_btn(self, name: str) -> None:
        self._set_active_effect(name)
        code = _EFFECTS[name]
        if code is None:
            return
        speed = self._speed_slider.get()
        self._run_async(
            self._controller.send(effect_command(code, speed)),
            on_success=lambda _: self._set_status(f"Effect: {name}"),
        )

    def _stop_effect(self) -> None:
        self._set_active_effect(None)
        self._send_color_debounced()

    def _set_active_effect(self, name: str | None) -> None:
        self._active_effect = name
        for btn_name, btn in self._effect_btns.items():
            if btn_name == name:
                btn.configure(border_color=_ACCENT, text_color=_ACCENT)
            else:
                btn.configure(border_color=_MUTED, text_color=_TEXT)

    # ──────────────────────────────────────────────────────────────────────
    # Colour sync helpers
    # ──────────────────────────────────────────────────────────────────────

    def _set_color_from_hex(self, color_hex: str, send: bool = True) -> None:
        try:
            r, g, b = hex_to_rgb(color_hex)
        except ValueError:
            r, g, b = 255, 102, 0
            color_hex = "#ff6600"
        self._set_color_from_rgb(r, g, b)
        if send:
            self._send_color_debounced()

    def _set_color_from_rgb(self, r: int, g: int, b: int) -> None:
        """Update all controls to reflect the given RGB value (no feedback loops)."""
        self._syncing = True
        try:
            color_hex = rgb_to_hex(r, g, b)
            self._hex_var.set(color_hex)
            self._preview_swatch.config(bg=color_hex)
            self._r_slider.set(r)
            self._g_slider.set(g)
            self._b_slider.set(b)
            # Update slider val labels
            if hasattr(self._r_slider, "_val_label"):
                self._r_slider._val_label.config(text=str(r))  # type: ignore[attr-defined]
            if hasattr(self._g_slider, "_val_label"):
                self._g_slider._val_label.config(text=str(g))  # type: ignore[attr-defined]
            if hasattr(self._b_slider, "_val_label"):
                self._b_slider._val_label.config(text=str(b))  # type: ignore[attr-defined]
            # Update slider gradient colours
            self._r_slider.set_color(f"#{r:02x}0000")
            self._g_slider.set_color(f"#00{g:02x}00")
            self._b_slider.set_color(f"#0000{b:02x}")
            self._wheel.set_rgb(r, g, b)
            self._state.color_hex = color_hex
            self._save_state()
            self._update_active_swatch(r, g, b)
        finally:
            self._syncing = False

    def _apply_rgb(self, r: int, g: int, b: int) -> None:
        """Called from wheel — updates sliders + hex only (wheel already updated)."""
        color_hex = rgb_to_hex(r, g, b)
        self._hex_var.set(color_hex)
        self._preview_swatch.config(bg=color_hex)
        self._r_slider.set(r)
        self._g_slider.set(g)
        self._b_slider.set(b)
        if hasattr(self._r_slider, "_val_label"):
            self._r_slider._val_label.config(text=str(r))  # type: ignore[attr-defined]
        if hasattr(self._g_slider, "_val_label"):
            self._g_slider._val_label.config(text=str(g))  # type: ignore[attr-defined]
        if hasattr(self._b_slider, "_val_label"):
            self._b_slider._val_label.config(text=str(b))  # type: ignore[attr-defined]
        self._r_slider.set_color(f"#{r:02x}0000")
        self._g_slider.set_color(f"#00{g:02x}00")
        self._b_slider.set_color(f"#0000{b:02x}")
        self._state.color_hex = color_hex
        self._save_state()
        self._update_active_swatch(r, g, b)

    def _update_active_swatch(self, r: int, g: int, b: int) -> None:
        """Mark the matching preset swatch as active (if any)."""
        for swatch, (_name, pr, pg, pb) in zip(self._swatches, _PRESETS):
            swatch.set_active(r == pr and g == pg and b == pb)

    # ──────────────────────────────────────────────────────────────────────
    # BLE send
    # ──────────────────────────────────────────────────────────────────────

    def _send_color_debounced(self) -> None:
        if self._debounce_job:
            self.after_cancel(self._debounce_job)
        self._debounce_job = self.after(60, self._send_current_color)

    def _send_current_color(self) -> None:
        self._debounce_job = None
        if not self._controller.is_connected:
            return
        try:
            r, g, b = hex_to_rgb(self._state.color_hex)
        except ValueError:
            return

        rr, gg, bb = apply_brightness(r, g, b, self._state.brightness)
        payload = color_command(rr, gg, bb)

        if not self._state.power_on:
            self._run_async(self._controller.send(power_command(False)))
            return

        self._run_async(
            self._controller.send(payload),
            on_success=lambda _: self._set_status("Color updated"),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Notify handler (called from asyncio thread)
    # ──────────────────────────────────────────────────────────────────────

    def _on_notify_raw(self, data: bytearray) -> None:
        state = parse_state(bytes(data))
        if not state:
            return
        r, g, b = state["r"], state["g"], state["b"]
        self.after(0, lambda: self._set_color_from_rgb(r, g, b))

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _set_dot(self, color: str) -> None:
        self._ble_dot.config(fg=color)

    def _set_status(self, text: str) -> None:
        self._status_text.set(text)

    def _save_state(self) -> None:
        self._config.save(self._state)

    def _run_async(
        self,
        coro: Any,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        future = self._loop.submit(coro)

        def poll() -> None:
            if not future.done():
                self.after(30, poll)
                return
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                if on_error:
                    on_error(exc)
                else:
                    self._set_status(f"Error: {exc}")
                return
            if on_success:
                on_success(result)

        self.after(30, poll)

    def _on_close(self) -> None:
        self._cancel_reconnect()
        try:
            self._config.save(self._state)
            self._loop.submit(self._controller.disconnect()).result(timeout=5)
        except Exception:
            pass
        finally:
            self._loop.stop()
            self.destroy()


# ──────────────────────────────────────────────────────────────────────────────


def _default_config_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return root / "GleamBLEled" / "config.json"
    return Path.home() / ".config" / "gleambled" / "config.json"


def run() -> None:
    app = LedApp()
    app.mainloop()
