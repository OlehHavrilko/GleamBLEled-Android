import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../ble/protocol.dart';
import '../models/device_info.dart';

class BleService extends ChangeNotifier {
  BluetoothDevice? _device;
  BluetoothCharacteristic? _writeChar;
  StreamSubscription<List<int>>? _notifySubscription;
  bool _isConnected = false;
  int _r = 255, _g = 128, _b = 0;
  bool _powerOn = true;

  bool get isConnected => _isConnected;
  int get r => _r;
  int get g => _g;
  int get b => _b;
  bool get powerOn => _powerOn;

  final _devicesController = StreamController<List<DeviceInfo>>.broadcast();
  Stream<List<DeviceInfo>> get discoveredDevices => _devicesController.stream;

  /// Scan for BLE LED controllers
  Future<void> scan({int duration = 5}) async {
    final results = <DeviceInfo>[];
    
    await FlutterBluePlus.startScan(timeout: Duration(seconds: duration));
    
    FlutterBluePlus.scanResults.listen((results) {
      for (final result in results) {
        final name = result.device.platformName;
        final addr = result.device.remoteId.str;
        
        if (_isKnownDevice(name)) {
          final rssi = result.rssi;
          results.add(DeviceInfo(
            name: name.isEmpty ? addr : name,
            address: addr,
            rssi: rssi,
            confidence: 'name',
          ));
        }
      }
      _devicesController.add(results);
    });
  }

  bool _isKnownDevice(String name) {
    if (name.isEmpty) return false;
    final upper = name.toUpperCase();
    return BleProtocol.knownDevicePrefixes.any((p) => upper.contains(p));
  }

  /// Connect to device
  Future<bool> connect(DeviceInfo device) async {
    try {
      await FlutterBluePlus.stopScan();
      
      final discovered = await FlutterBluePlus.scanResults.firstWhere(
        (r) => r.any((d) => d.device.remoteId.str == device.address),
      );
      
      _device = discovered.first.device;
      await _device!.connect(timeout: const Duration(seconds: 12));
      
      // Find write characteristic
      final services = await _device!.discoverServices();
      for (final service in services) {
        for (final char in service.characteristics) {
          if (char.uuid.str.contains('fff3') || 
              char.properties.write || 
              char.properties.writeWithoutResponse) {
            _writeChar = char;
            break;
          }
        }
      }
      
      _isConnected = true;
      notifyListeners();
      
      // Subscribe to notifications
      await _subscribeNotify();
      
      // Auto-reconnect setup
      _device!.connectionState.listen((state) {
        if (state == BluetoothConnectionState.disconnected) {
          _isConnected = false;
          notifyListeners();
          _autoReconnect(device);
        }
      });
      
      return true;
    } catch (e) {
      debugPrint('Connection failed: $e');
      return false;
    }
  }

  Future<void> _subscribeNotify() async {
    final services = await _device!.discoverServices();
    for (final service in services) {
      for (final char in service.characteristics) {
        if (char.properties.notify) {
          await char.setNotifyValue(true);
          _notifySubscription = char.onValueReceived.listen((value) {
            final state = BleProtocol.parseState(value);
            if (state != null) {
              _r = state['r']!;
              _g = state['g']!;
              _b = state['b']!;
              notifyListeners();
            }
          });
          break;
        }
      }
    }
  }

  Future<void> _autoReconnect(DeviceInfo device) async {
    for (int i = 0; i < 5; i++) {
      await Future.delayed(const Duration(seconds: 5));
      if (await connect(device)) return;
    }
  }

  /// Send color command
  Future<void> setColor(int r, int g, int b) async {
    if (!_isConnected || _writeChar == null) return;
    _r = r; _g = g; _b = b;
    final cmd = BleProtocol.cmdColor(r, g, b);
    await _writeChar!.write(cmd);
    notifyListeners();
  }

  /// Power on/off
  Future<void> setPower(bool on) async {
    if (!_isConnected || _writeChar == null) return;
    _powerOn = on;
    final cmd = on ? BleProtocol.cmdPowerOn() : BleProtocol.cmdPowerOff();
    await _writeChar!.write(cmd);
    notifyListeners();
  }

  /// Set effect
  Future<void> setEffect(int effectCode, int speed) async {
    if (!_isConnected || _writeChar == null) return;
    final cmd = BleProtocol.cmdEffect(effectCode, speed);
    await _writeChar!.write(cmd);
  }

  /// Disconnect
  Future<void> disconnect() async {
    await _notifySubscription?.cancel();
    await _device?.disconnect();
    _isConnected = false;
    _writeChar = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _devicesController.close();
    disconnect();
    super.dispose();
  }
}
