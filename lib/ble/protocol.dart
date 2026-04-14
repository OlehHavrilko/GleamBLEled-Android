/// BLE Protocol for ELK-BLEDOM and compatible LED controllers.
/// Ported from Python GleamBLEled.

class BleProtocol {
  // UUIDs
  static const serviceUuid = '0000fff0-0000-1000-8000-00805f9b34fb';
  static const writeUuid = '0000fff3-0000-1000-8000-00805f9b34fb';
  static const notifyUuid = '0000fff4-0000-1000-8000-00805f9b34fb';

  static const knownServiceUuids = [
    '0000ffd5-0000-1000-8000-00805f9b34fb',
    '0000ffe5-0000-1000-8000-00805f9b34fb',
    '0000fff0-0000-1000-8000-00805f9b34fb',
    '0000cc01-0000-1000-8000-00805f9b34fb',
  ];

  static const knownDevicePrefixes = [
    'QHM-', 'ELK-', 'LEDNET', 'LEDBLUE', 'LEDBLE', 'MAGIC',
    'TRIONES', 'HJ-', 'BLE-LED', 'LED_', 'ILC', 'ZENGGE',
    'MELK', 'HUAWEI_LED', 'SP110E', 'ELK-BLEDOM',
  ];

  /// Build color command: 7E 00 05 03 RR GG BB 00 EF
  static List<int> cmdColor(int r, int g, int b) {
    return [0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF];
  }

  /// Build power on command: 7E 00 04 F0 00 01 FF 00 EF
  static List<int> cmdPowerOn() {
    return [0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF];
  }

  /// Build power off command: 7E 00 04 F0 00 00 FF 00 EF
  static List<int> cmdPowerOff() {
    return [0x7E, 0x00, 0x04, 0xF0, 0x00, 0x00, 0xFF, 0x00, 0xEF];
  }

  /// Build effect command: 7E 00 03 CC SS 00 EF
  static List<int> cmdEffect(int effectCode, int speed) {
    return [0x7E, 0x00, 0x03, effectCode, speed, 0x00, 0xEF];
  }

  /// Parse state notification: 7E-07-05-03-RR-GG-BB-00-EF
  static Map<String, int>? parseState(List<int> raw) {
    if (raw.length >= 9 && raw[0] == 0x7E && raw[8] == 0xEF) {
      return {'r': raw[4], 'g': raw[5], 'b': raw[6]};
    }
    return null;
  }

  /// Effect codes
  static const effectBreathing = 0x25;
  static const effectCycle = 0x26;
  static const effectStrobe = 0x27;
  static const effectFlash = 0x28;
}
