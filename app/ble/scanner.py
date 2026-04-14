# pyright: reportMissingImports=false
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from bleak import BleakClient, BleakScanner

from app.constants import (
    KNOWN_DEVICE_NAME_HINTS,
    KNOWN_SERVICE_UUIDS,
    PREFERRED_WRITE_UUIDS,
)
from app.models import DeviceInfo
from app.ble.protocol import cmd_color, cmd_power_on


@dataclass(slots=True)
class ProbeCandidate:
    name: str
    address: str
    rssi: int | None


def _is_led_controller_name(name: str | None) -> bool:
    if not name:
        return False
    upper_name = name.upper()
    return any(
        upper_name.startswith(prefix.upper()) for prefix in KNOWN_DEVICE_NAME_HINTS
    )


def _has_known_service(service_uuids: list[str] | None) -> bool:
    if not service_uuids:
        return False
    seen = {str(uuid).lower() for uuid in service_uuids}
    return any(uuid in seen for uuid in KNOWN_SERVICE_UUIDS)


class GleamScanner:
    def __init__(self) -> None:
        self._probe_cmd = cmd_color(255, 0, 0)
        self._restore_cmd = cmd_power_on()
        # Кеш raw BLEDevice объектов — нужен на Windows для передачи в BleakClient
        # вместо строки адреса (иначе WinRT-бэкенд не может найти устройство).
        self._ble_device_cache: dict[str, Any] = {}

    def get_ble_device(self, address: str) -> Any | None:
        """Возвращает кешированный BLEDevice по адресу (или None)."""
        return self._ble_device_cache.get(address.upper())

    async def scan(
        self,
        duration: float = 5.0,
        on_found: Callable[[DeviceInfo], None] | None = None,
        include_unknown: bool = False,
    ) -> tuple[list[DeviceInfo], list[ProbeCandidate]]:
        results: dict[str, DeviceInfo] = {}
        unknowns: dict[str, ProbeCandidate] = {}

        def detection_callback(device: Any, advertisement_data: Any) -> None:
            name = getattr(device, "name", None)
            address = str(getattr(device, "address", "")).strip()
            if not address:
                return

            # Кешируем raw BLEDevice всегда — нужно для Windows-подключения
            self._ble_device_cache[address.upper()] = device

            rssi = getattr(advertisement_data, "rssi", None)
            service_uuids = getattr(advertisement_data, "service_uuids", None)

            found: DeviceInfo | None = None
            if _is_led_controller_name(name):
                found = DeviceInfo(
                    name=name or address,
                    address=address,
                    rssi=rssi,
                    confidence="name",
                )
            elif _has_known_service(service_uuids):
                found = DeviceInfo(
                    name=name or f"Unknown_{address[-5:]}",
                    address=address,
                    rssi=rssi,
                    confidence="uuid",
                )

            if found:
                prev = results.get(address)
                if prev is None or ((found.rssi or -999) > (prev.rssi or -999)):
                    results[address] = found
                    if on_found:
                        on_found(found)
                return

            if include_unknown and address not in unknowns:
                unknowns[address] = ProbeCandidate(
                    name=name or f"Unknown_{address[-5:]}",
                    address=address,
                    rssi=rssi,
                )

        async with BleakScanner(detection_callback=detection_callback):
            await asyncio.sleep(duration)

        devices = sorted(
            results.values(),
            key=lambda item: item.rssi if item.rssi is not None else -999,
            reverse=True,
        )
        unknown_list = sorted(
            unknowns.values(),
            key=lambda item: item.rssi if item.rssi is not None else -999,
            reverse=True,
        )
        return devices, unknown_list

    async def probe_unknown(self, candidate: ProbeCandidate) -> DeviceInfo | None:
        ble_device = self.get_ble_device(candidate.address) or candidate.address
        try:
            async with BleakClient(ble_device, timeout=10.0) as client:
                services = client.services
                writable: set[str] = set()
                for service in services:
                    for char in service.characteristics:
                        if any(prop.startswith("write") for prop in char.properties):
                            writable.add(char.uuid.lower())

                for uuid_candidate in PREFERRED_WRITE_UUIDS:
                    if uuid_candidate not in writable:
                        continue
                    try:
                        await client.write_gatt_char(
                            uuid_candidate, self._probe_cmd, response=False
                        )
                        await asyncio.sleep(0.3)
                        await client.write_gatt_char(
                            uuid_candidate, self._restore_cmd, response=False
                        )
                    except Exception:
                        continue
                    return DeviceInfo(
                        name=candidate.name,
                        address=candidate.address,
                        rssi=candidate.rssi,
                        confidence="probe",
                        write_uuid=uuid_candidate,
                    )
        except Exception:
            return None
        return None
