from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.constants import DEFAULT_BRIGHTNESS, DEFAULT_COLOR
from app.utils import hex_to_rgb, rgb_to_hex


@dataclass(slots=True)
class DeviceInfo:
    name: str
    address: str
    rssi: int | None = None
    confidence: str = "name"
    write_uuid: str | None = None


@dataclass(slots=True)
class RememberedDevice:
    address: str
    name: str
    write_uuid: str | None = None
    confidence: str = "name"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "address": self.address,
            "name": self.name,
            "confidence": self.confidence,
        }
        if self.write_uuid:
            payload["write_uuid"] = self.write_uuid
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RememberedDevice | None:
        address = str(data.get("address", "")).strip()
        if not address:
            return None
        write_uuid_raw = str(data.get("write_uuid", "")).strip().lower()
        return cls(
            address=address,
            name=str(data.get("name", address)),
            write_uuid=write_uuid_raw or None,
            confidence=str(data.get("confidence", "name")),
        )

    @classmethod
    def from_device(cls, device: DeviceInfo) -> RememberedDevice:
        return cls(
            address=device.address,
            name=device.name,
            write_uuid=device.write_uuid,
            confidence=device.confidence,
        )


@dataclass(slots=True)
class AppState:
    last_device: RememberedDevice | None = None
    color_hex: str = DEFAULT_COLOR
    brightness: float = DEFAULT_BRIGHTNESS
    power_on: bool = True

    @property
    def last_device_address(self) -> str:
        return self.last_device.address if self.last_device else ""

    @property
    def last_device_name(self) -> str:
        return self.last_device.name if self.last_device else ""

    def remember_device(self, device: DeviceInfo) -> None:
        self.last_device = RememberedDevice.from_device(device)

    def to_dict(self) -> dict[str, Any]:
        red, green, blue = hex_to_rgb(self.color_hex)
        return {
            "last_device": self.last_device.to_dict() if self.last_device else None,
            "last_color": [red, green, blue],
            "brightness": round(max(0.0, min(1.0, self.brightness)), 3),
            "power_on": self.power_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppState:
        brightness_raw = data.get("brightness", DEFAULT_BRIGHTNESS)
        try:
            brightness_value = float(brightness_raw)
        except (TypeError, ValueError):
            brightness_value = DEFAULT_BRIGHTNESS

        if brightness_value > 1.0:
            brightness_value /= 100.0
        brightness_value = max(0.0, min(1.0, brightness_value))

        remembered: RememberedDevice | None = None
        last_device_raw = data.get("last_device")
        if isinstance(last_device_raw, dict):
            remembered = RememberedDevice.from_dict(last_device_raw)
        elif data.get("last_device_address"):
            remembered = RememberedDevice(
                address=str(data.get("last_device_address", "")),
                name=str(
                    data.get("last_device_name", data.get("last_device_address", ""))
                ),
            )

        color_hex = DEFAULT_COLOR
        last_color = data.get("last_color")
        if isinstance(last_color, list) and len(last_color) == 3:
            try:
                color_hex = rgb_to_hex(
                    int(last_color[0]),
                    int(last_color[1]),
                    int(last_color[2]),
                )
            except (TypeError, ValueError):
                color_hex = DEFAULT_COLOR
        elif "color_hex" in data:
            color_hex = str(data.get("color_hex", DEFAULT_COLOR))

        return cls(
            last_device=remembered,
            color_hex=color_hex,
            brightness=brightness_value,
            power_on=bool(data.get("power_on", True)),
        )
