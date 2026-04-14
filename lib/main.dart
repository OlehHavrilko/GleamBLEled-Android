import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'ble/protocol.dart';
import 'models/device_info.dart';
import 'screens/home_screen.dart';
import 'services/ble_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await FlutterBluePlus.setLogLevel(LogLevel.debug);
  runApp(const GleamBLEledApp());
}

class GleamBLEledApp extends StatelessWidget {
  const GleamBLEledApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GleamBLEled',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        colorScheme: ColorScheme.dark(
          primary: Colors.orange,
          secondary: Colors.cyan,
          surface: const Color(0xFF1E1E1E),
        ),
      ),
      home: const HomeScreen(),
    );
  }
}
