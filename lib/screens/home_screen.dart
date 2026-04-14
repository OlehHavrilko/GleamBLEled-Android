import 'package:flutter/material.dart';
import 'package:flutter_colorpicker/flutter_colorpicker.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../ble/protocol.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late BleService _bleService;
  Color _currentColor = const Color(0xFFFF6600);

  @override
  void initState() {
    super.initState();
    _bleService = BleService();
    // start scanning automatically
    _bleService.scan();
  }

  @override
  void dispose() {
    _bleService.dispose();
    super.dispose();
  }

  void _pickColor() async {
    Color? picked = await showDialog<Color>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Pick Color'),
        content: SingleChildScrollView(
          child: ColorPicker(
            pickerColor: _currentColor,
            onColorChanged: (c) => _currentColor = c,
            enableAlpha: false,
            showLabel: true,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(c).pop(), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.of(c).pop(_currentColor), child: const Text('Select')),
        ],
      ),
    );
    if (picked != null) {
      setState(() => _currentColor = picked);
      await _bleService.setColor(picked.red, picked.green, picked.blue);
    }
  }

  void _togglePower() async {
    final newState = !_bleService.powerOn;
    await _bleService.setPower(newState);
    setState(() {});
  }

  void _applyEffect(int code) async {
    await _bleService.setEffect(code, 50);
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _bleService,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('GleamBLEled Android'),
          actions: [
            IconButton(icon: const Icon(Icons.refresh), onPressed: () => _bleService.scan()),
          ],
        ),
        body: Consumer<BleService>(
          builder: (c, service, _) {
            return Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.bluetooth),
                  title: Text(service.isConnected ? 'Connected' : 'Disconnected'),
                ),
                ElevatedButton(onPressed: _togglePower, child: Text(service.powerOn ? 'Turn Off' : 'Turn On')),
                ElevatedButton(onPressed: _pickColor, child: const Text('Pick Color')),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  children: [
                    ElevatedButton(onPressed: () => _applyEffect(BleProtocol.effectBreathing), child: const Text('Breathing')),
                    ElevatedButton(onPressed: () => _applyEffect(BleProtocol.effectCycle), child: const Text('Cycle')),
                    ElevatedButton(onPressed: () => _applyEffect(BleProtocol.effectStrobe), child: const Text('Strobe')),
                    ElevatedButton(onPressed: () => _applyEffect(BleProtocol.effectFlash), child: const Text('Flash')),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
