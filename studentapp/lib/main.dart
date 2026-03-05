import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'theme/app_theme.dart';
import 'screens/enrollment_input_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Force portrait mode
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Dark status bar
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Colors.black,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  runApp(const MarkinApp());
}

class MarkinApp extends StatelessWidget {
  const MarkinApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MARKIN',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const EnrollmentInputScreen(),
    );
  }
}
