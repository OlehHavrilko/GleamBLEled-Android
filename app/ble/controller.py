# pyright: reportMissingImports=false
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from bleak import BleakClient, BleakScanner

from app.constants import DEFAULT_CONNECT_TIMEOUT, PREFERRED_WRITE_UUIDS
from app.ble.protocol import NOTIFY_UUID


class BleLedController:
    def __init__(self, on_disconnect: Callable[[], None] | None = None) -> None:
        self._client: BleakClient | None = None
        self._write_uuid: str | None = None
        self._connected_address: str = ""
        self._on_disconnect = on_disconnect
        self._notify_subscribed: bool = False

    @property
    def connected_address(self) -> str:
        return self._connected_address

    @property
    def write_uuid(self) -> str | None:
        return self._write_uuid

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    async def connect(
        self,
        address: str,
        timeout: float = DEFAULT_CONNECT_TIMEOUT,
        preferred_write_uuid: str | None = None,
        ble_device: Any = None,
    ) -> None:
        """
        Подключиться к BLE-устройству.

        ble_device — raw BLEDevice из BleakScanner (предпочтительно на Windows).
        Если не передан — выполняется BleakScanner.find_device_by_address(),
        что надёжнее передачи голой строки адреса в WinRT-бэкенде.
        """
        await self.disconnect()

        target: Any = ble_device
        if target is None:
            # Сканируем до timeout секунд, чтобы получить BLEDevice объект.
            # На Windows передача строки адреса в BleakClient ненадёжна.
            target = await BleakScanner.find_device_by_address(address, timeout=timeout)
            if target is None:
                raise RuntimeError(f"Device with address {address} was not found.")

        client = BleakClient(target, disconnected_callback=self._handle_disconnect)
        await client.connect(timeout=timeout)
        write_uuid = self._detect_write_uuid(client, preferred_write_uuid)
        self._client = client
        self._connected_address = address
        self._write_uuid = write_uuid

    async def disconnect(self) -> None:
        if not self._client:
            return
        try:
            if self._client.is_connected:
                # Отписываемся от notify перед отключением
                if self._notify_subscribed:
                    try:
                        await self._client.stop_notify(NOTIFY_UUID)
                    except Exception:
                        pass
                    self._notify_subscribed = False
                await self._client.disconnect()
        finally:
            self._client = None
            self._write_uuid = None
            self._connected_address = ""
            self._notify_subscribed = False

    async def send(self, payload: bytes) -> None:
        if not self._client or not self._client.is_connected:
            raise RuntimeError("Device is not connected")
        if not self._write_uuid:
            raise RuntimeError("Write characteristic UUID is not resolved")
        await self._client.write_gatt_char(self._write_uuid, payload, response=False)

    async def ping(self) -> None:
        await asyncio.sleep(0)

    async def subscribe_notify(self, callback: Callable[[bytearray], None]) -> bool:
        """
        Подписаться на notify-характеристику (NOTIFY_UUID fff4).
        Возвращает True если подписка установлена, False если не поддерживается.
        callback вызывается из asyncio-потока; не обращайтесь к Tk-виджетам напрямую.
        """
        if not self._client or not self._client.is_connected:
            return False

        # Проверяем, есть ли notify-характеристика
        try:
            services = self._client.services
        except Exception:
            return False

        notify_uuid_lower = NOTIFY_UUID.lower()
        has_notify = any(
            char.uuid.lower() == notify_uuid_lower
            for service in services
            for char in service.characteristics
            if "notify" in char.properties
        )
        if not has_notify:
            return False

        try:
            await self._client.start_notify(NOTIFY_UUID, callback)
            self._notify_subscribed = True
            return True
        except Exception:
            return False

    def _detect_write_uuid(
        self, client: BleakClient, preferred_write_uuid: str | None
    ) -> str:
        services = client.services
        writable: set[str] = set()
        for service in services:
            for char in service.characteristics:
                if any(prop.startswith("write") for prop in char.properties):
                    writable.add(char.uuid.lower())

        if preferred_write_uuid and preferred_write_uuid.lower() in writable:
            return preferred_write_uuid.lower()

        for candidate in PREFERRED_WRITE_UUIDS:
            if candidate in writable:
                return candidate

        if writable:
            return sorted(writable)[0]

        raise RuntimeError("No writable GATT characteristic found")

    def _handle_disconnect(self, _client: Any) -> None:
        self._client = None
        self._write_uuid = None
        self._connected_address = ""
        self._notify_subscribed = False
        if self._on_disconnect:
            self._on_disconnect()
