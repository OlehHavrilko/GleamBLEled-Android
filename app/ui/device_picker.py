# app/ui/device_picker.py
"""
Modal-диалог выбора BLE-устройства из списка с RSSI-барами.

Использование:
    dialog = DevicePickerDialog(parent, devices, unknowns)
    dialog.wait_result()           # блокирует UI до закрытия
    if dialog.action == "connect":
        connect(dialog.selected_device)
    elif dialog.action == "probe":
        probe(dialog.selected_device)
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from app.models import DeviceInfo
from app.ble.scanner import ProbeCandidate
from app.utils import rssi_to_bars

# Цвета, дублируем из app.py чтобы не создавать круговую зависимость
_DOT_GREEN = "#2f9e44"
_DOT_YELLOW = "#f59f00"
_DOT_RED = "#c92a2a"


class DevicePickerDialog(ctk.CTkToplevel):
    """
    Modal-окно выбора устройства.

    Атрибуты после закрытия:
      action: "connect" | "probe" | "cancel"
      selected_device: DeviceInfo | None
    """

    def __init__(
        self,
        parent: ctk.CTk,
        devices: list[DeviceInfo],
        unknowns: list[ProbeCandidate],
        on_connect: Callable[[DeviceInfo], None],
        on_probe: Callable[[ProbeCandidate], None],
    ) -> None:
        super().__init__(parent)
        self.title("Выбор устройства")
        self.geometry("560x420")
        self.minsize(480, 320)
        self.resizable(True, True)

        # Сделать modal
        self.transient(parent)
        self.grab_set()

        self._on_connect = on_connect
        self._on_probe = on_probe

        # Внутренний state: (DeviceInfo | ProbeCandidate | None, is_unknown: bool)
        self._selected_item: DeviceInfo | ProbeCandidate | None = None
        self._selected_is_unknown: bool = False

        # Все строки: (row_frame, item, is_unknown)
        self._rows: list[tuple[ctk.CTkFrame, DeviceInfo | ProbeCandidate, bool]] = []
        self._selected_row_frame: ctk.CTkFrame | None = None

        self._build(devices, unknowns)

        # Центрируем относительно родителя
        self.after(50, self._center)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    # ──────────────────────────────────────────────────────────────────────
    # Построение UI
    # ──────────────────────────────────────────────────────────────────────

    def _build(self, devices: list[DeviceInfo], unknowns: list[ProbeCandidate]) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Заголовок
        ctk.CTkLabel(
            self,
            text="Выберите LED-контроллер",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        # Прокручиваемый список
        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        scroll.grid_columnconfigure(0, weight=1)

        row_idx = 0
        if devices:
            ctk.CTkLabel(
                scroll,
                text="Распознанные LED-контроллеры",
                text_color="#aaaaaa",
                font=ctk.CTkFont(size=12),
                anchor="w",
            ).grid(row=row_idx, column=0, sticky="w", padx=8, pady=(6, 2))
            row_idx += 1
            for device in devices:
                frame = self._make_row(scroll, row_idx, device, is_unknown=False)
                self._rows.append((frame, device, False))
                row_idx += 1

        if unknowns:
            ctk.CTkLabel(
                scroll,
                text="Неопознанные устройства (требуют зондирования)",
                text_color="#888888",
                font=ctk.CTkFont(size=12),
                anchor="w",
            ).grid(row=row_idx, column=0, sticky="w", padx=8, pady=(12, 2))
            row_idx += 1
            for candidate in unknowns:
                # Оборачиваем в DeviceInfo для удобства отображения
                device = DeviceInfo(
                    name=candidate.name,
                    address=candidate.address,
                    rssi=candidate.rssi,
                    confidence="probe",
                )
                frame = self._make_row(scroll, row_idx, device, is_unknown=True)
                self._rows.append((frame, candidate, True))
                row_idx += 1

        # Предвыбираем первую строку
        if self._rows:
            self._select_row(self._rows[0])

        # Нижняя панель кнопок
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 14))
        btn_bar.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_connect = ctk.CTkButton(
            btn_bar,
            text="Подключить",
            fg_color=_DOT_GREEN,
            hover_color="#237a34",
            command=self._action_connect,
        )
        self._btn_connect.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._btn_probe = ctk.CTkButton(
            btn_bar,
            text="Зондировать",
            fg_color="#5c5f66",
            hover_color="#373a40",
            command=self._action_probe,
        )
        self._btn_probe.grid(row=0, column=1, sticky="ew", padx=4)

        ctk.CTkButton(
            btn_bar,
            text="Отмена",
            fg_color=_DOT_RED,
            hover_color="#a21e1e",
            command=self._cancel,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self._update_buttons()

    def _make_row(
        self,
        parent: ctk.CTkScrollableFrame,
        grid_row: int,
        device: DeviceInfo,
        is_unknown: bool,
    ) -> ctk.CTkFrame:
        bars = rssi_to_bars(device.rssi)
        rssi_str = f"  {device.rssi} dBm" if device.rssi else ""
        confidence_badge = {
            "name": "🔵 name",
            "uuid": "🟡 uuid",
            "probe": "🔴 ?",
        }.get(device.confidence, "")

        frame = ctk.CTkFrame(parent, cursor="hand2")
        frame.grid(row=grid_row, column=0, sticky="ew", padx=4, pady=2)
        frame.grid_columnconfigure(1, weight=1)

        # RSSI бары
        ctk.CTkLabel(
            frame,
            text=bars,
            font=ctk.CTkFont(family="monospace", size=13),
            width=54,
            anchor="w",
        ).grid(row=0, column=0, padx=(8, 4), pady=6)

        # Имя + адрес
        name_col = ctk.CTkFrame(frame, fg_color="transparent")
        name_col.grid(row=0, column=1, sticky="ew", pady=6)
        name_col.grid_columnconfigure(0, weight=1)

        name_text = f"[?] {device.name}" if is_unknown else device.name
        ctk.CTkLabel(
            name_col,
            text=name_text,
            font=ctk.CTkFont(size=14, weight="bold" if not is_unknown else "normal"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            name_col,
            text=f"{device.address}{rssi_str}",
            text_color="#888888",
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=1, column=0, sticky="w")

        # Бейдж confidence
        ctk.CTkLabel(
            frame,
            text=confidence_badge,
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa",
            width=60,
            anchor="e",
        ).grid(row=0, column=2, padx=(4, 8), pady=6)

        # Привязываем клик к выделению строки — сохраняем ссылку на кортеж после добавления
        # Используем partial-bind через lambda, захватываем индекс после append
        frame.bind("<Button-1>", lambda _e, f=frame: self._on_row_click(f))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda _e, f=frame: self._on_row_click(f))
            for grandchild in child.winfo_children():
                grandchild.bind("<Button-1>", lambda _e, f=frame: self._on_row_click(f))

        return frame

    # ──────────────────────────────────────────────────────────────────────
    # Выделение строки
    # ──────────────────────────────────────────────────────────────────────

    def _on_row_click(self, clicked_frame: ctk.CTkFrame) -> None:
        for row_tuple in self._rows:
            if row_tuple[0] is clicked_frame:
                self._select_row(row_tuple)
                return

    def _select_row(
        self, row_tuple: tuple[ctk.CTkFrame, DeviceInfo | ProbeCandidate, bool]
    ) -> None:
        frame, item, is_unknown = row_tuple

        # Снять выделение с предыдущей
        if self._selected_row_frame and self._selected_row_frame is not frame:
            self._selected_row_frame.configure(fg_color=("gray86", "gray17"))

        self._selected_row_frame = frame
        frame.configure(fg_color=("gray75", "gray28"))

        self._selected_item = item
        self._selected_is_unknown = is_unknown
        self._update_buttons()

    def _update_buttons(self) -> None:
        if self._selected_item is None:
            self._btn_connect.configure(state="disabled")
            self._btn_probe.configure(state="disabled")
        elif self._selected_is_unknown:
            self._btn_connect.configure(state="disabled")
            self._btn_probe.configure(state="normal")
        else:
            self._btn_connect.configure(state="normal")
            self._btn_probe.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────
    # Действия
    # ──────────────────────────────────────────────────────────────────────

    def _action_connect(self) -> None:
        if not self._selected_item or self._selected_is_unknown:
            return
        device = self._selected_item
        assert isinstance(device, DeviceInfo)
        self.grab_release()
        self.destroy()
        self._on_connect(device)

    def _action_probe(self) -> None:
        if not self._selected_item or not self._selected_is_unknown:
            return
        candidate = self._selected_item
        assert isinstance(candidate, ProbeCandidate)
        self.grab_release()
        self.destroy()
        self._on_probe(candidate)

    def _cancel(self) -> None:
        self.grab_release()
        self.destroy()

    # ──────────────────────────────────────────────────────────────────────
    # Позиционирование
    # ──────────────────────────────────────────────────────────────────────

    def _center(self) -> None:
        parent = self.master
        self.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width() // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"{w}x{h}+{px - w // 2}+{py - h // 2}")
