import 'dart:async';
import 'package:flutter/material.dart';
import '../services/ble_service.dart';
import '../services/api_service.dart';
import '../models/active_class.dart';
import '../theme/app_theme.dart';
import 'package:google_fonts/google_fonts.dart';

/// InheritedWidget that exposes BLE token, device name, and active class to descendants.
class BleGatewayData extends InheritedWidget {
  final String? bleToken;
  final String? deviceName;
  final ActiveClassInfo? activeClass;

  const BleGatewayData({
    super.key,
    required this.bleToken,
    required this.deviceName,
    required this.activeClass,
    required super.child,
  });

  static BleGatewayData? of(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<BleGatewayData>();
  }

  @override
  bool updateShouldNotify(BleGatewayData oldWidget) =>
      bleToken != oldWidget.bleToken ||
      deviceName != oldWidget.deviceName ||
      activeClass != oldWidget.activeClass;
}

class BleGatewayScreen extends StatefulWidget {
  final Widget child;
  final String deviceName;
  final Map<String, dynamic>? activeClass;
  final Map<String, dynamic>? student;

  const BleGatewayScreen({
    super.key,
    required this.child,
    required this.deviceName,
    this.activeClass,
    this.student,
  });

  @override
  State<BleGatewayScreen> createState() => _BleGatewayScreenState();
}

class _BleGatewayScreenState extends State<BleGatewayScreen>
    with SingleTickerProviderStateMixin {
  final BleService _bleService = BleService();
  final ApiService _apiService = ApiService();
  BleStatus _status = BleStatus.idle;
  String? _error;
  bool _showSuccess = false;
  bool _passed = false;
  bool _verifying = false; // backend token check in progress
  ActiveClassInfo? _activeClass; // Resolved active class from device

  late AnimationController _pulseController;
  StreamSubscription? _statusSub;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat();

    _statusSub = _bleService.statusStream.listen((status) async {
      if (!mounted || _passed) return; // Stop listening to new tokens for GATE verification once passed
      setState(() {
        _status = status;
        _error = _bleService.error;
      });

      if (status == BleStatus.found) {
        await _verifyToken();
      }
    });
    // Start scan for the specific device
    _bleService.scan(targetDeviceName: widget.deviceName);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _statusSub?.cancel();
    super.dispose();
  }

  Future<void> _verifyToken() async {
    final token = _bleService.bleToken;
    final deviceName = _bleService.deviceName;

    if (token == null || deviceName == null) {
      setState(() {
        _verifying = false;
        _status = BleStatus.error;
        _error = 'Signal found but no token received. Try again.';
      });
      _bleService.reset();
      return;
    }

    setState(() => _verifying = true);

    try {
      final result = await _apiService.verifyBleToken(
        token,
        deviceName: deviceName,
      );
      if (!mounted) return;

      final valid = result['valid'] == true;
      if (valid) {
        // Parse active class info if available
        final activeClassData = result['active_class'];
        if (activeClassData != null &&
            activeClassData is Map<String, dynamic>) {
          _activeClass = ActiveClassInfo.fromJson(activeClassData);
        }
        _unlockApp();
      } else {
        setState(() {
          _verifying = false;
          _status = BleStatus.error;
          _error = 'Signal verification failed. Please try again.';
        });
        _bleService.reset();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _verifying = false;
        _status = BleStatus.error;
        _error = 'Network error. Check connection and try again.';
      });
      _bleService.reset();
    }
  }

  void _unlockApp() {
    setState(() {
      _verifying = false;
      _showSuccess = true;
    });
    Future.delayed(const Duration(milliseconds: 800), () {
      if (mounted)
        setState(() {
          _showSuccess = false;
          _passed = true;
        });
    });
  }

  Future<void> _handleVerify() async {
    await _bleService.scan(targetDeviceName: widget.deviceName);
  }

  @override
  Widget build(BuildContext context) {
    // If connected and past success animation, show the app
    // Wrap child in BleGatewayData so descendants can read the token
    if (_passed) {
      return BleGatewayData(
        bleToken: _bleService.bleToken,
        deviceName: _bleService.deviceName,
        activeClass: _activeClass,
        child: widget.child,
      );
    }

    return Scaffold(
      backgroundColor: AppColors.bgPrimary,
      body: SafeArea(
        child: Stack(
          children: [
            // Brand header
            Positioned(
              top: 48,
              left: 0,
              right: 0,
              child: Center(
                child: Text(
                  'MARKIN',
                  style: GoogleFonts.bricolageGrotesque(
                    fontSize: 40,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: -0.5,
                  ),
                ),
              ),
            ),

            // Central connect button
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Pulsing rings for scanning
                  SizedBox(
                    width: 160,
                    height: 160,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        if (_status == BleStatus.scanning) ...[
                          AnimatedBuilder(
                            animation: _pulseController,
                            builder: (context, child) {
                              return Transform.scale(
                                scale: 1.0 + _pulseController.value * 0.6,
                                child: Opacity(
                                  opacity: 1.0 - _pulseController.value,
                                  child: Container(
                                    width: 128,
                                    height: 128,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      border: Border.all(
                                        color: Colors.white.withValues(
                                          alpha: 0.1,
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ],
                        // Main button
                        GestureDetector(
                          onTap: (_status == BleStatus.scanning || _showSuccess)
                              ? null
                              : _handleVerify,
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 500),
                            width: 128,
                            height: 128,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: _status == BleStatus.scanning
                                  ? Colors.white.withValues(alpha: 0.05)
                                  : _showSuccess
                                  ? const Color(0xFF10B981)
                                  : Colors.white,
                              boxShadow:
                                  _status == BleStatus.idle ||
                                      _status == BleStatus.error
                                  ? [
                                      BoxShadow(
                                        color: Colors.white.withValues(
                                          alpha: 0.08,
                                        ),
                                        blurRadius: 40,
                                        spreadRadius: -10,
                                      ),
                                    ]
                                  : null,
                            ),
                            child: Center(
                              child: _status == BleStatus.scanning
                                  ? Container(
                                      width: 16,
                                      height: 16,
                                      decoration: const BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: Colors.white,
                                      ),
                                    )
                                  : _showSuccess
                                  ? const Icon(
                                      Icons.check_circle,
                                      size: 48,
                                      color: Colors.white,
                                    )
                                  : const Icon(
                                      Icons.cell_tower,
                                      size: 40,
                                      color: Colors.black,
                                    ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 64),

                  // Status text
                  Text(
                    _verifying
                        ? 'Verifying signal...'
                        : _status == BleStatus.scanning
                        ? 'Searching for signal...'
                        : _showSuccess
                        ? 'Verified'
                        : 'Connect to classroom',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 2,
                      color: AppColors.textSecondary,
                    ),
                  ),

                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.error.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: AppColors.error.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.error_outline,
                            size: 12,
                            color: AppColors.error,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _error!,
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                color: AppColors.error,
                              ),
                              overflow: TextOverflow.visible,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // Footer
            Positioned(
              bottom: 48,
              left: 0,
              right: 0,
              child: Center(
                child: Text(
                  'SECURE ATTENDANCE',
                  style: GoogleFonts.inter(
                    fontSize: 10,
                    letterSpacing: 2,
                    color: Colors.white.withValues(alpha: 0.2),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
