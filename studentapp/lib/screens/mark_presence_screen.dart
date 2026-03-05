import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'widgets/camera_widget.dart';
import 'ble_gateway_screen.dart';
import '../services/ble_service.dart';
import 'package:google_fonts/google_fonts.dart';

class MarkPresenceScreen extends StatefulWidget {
  final String sessionId;
  final String groupId;
  final String deviceName;

  const MarkPresenceScreen({
    super.key,
    required this.sessionId,
    required this.groupId,
    required this.deviceName,
  });

  @override
  State<MarkPresenceScreen> createState() => _MarkPresenceScreenState();
}

enum _FlowStep { capture, processing, success, error }

class _MarkPresenceScreenState extends State<MarkPresenceScreen> {
  final ApiService _apiService = ApiService();
  final BleService _bleService = BleService();
  _FlowStep _step = _FlowStep.capture;
  String? _error;
  String? _matchedName;
  String? _matchedEnrollment;
  String? _timestamp;
  String? _processingMessage;

  @override
  void initState() {
    super.initState();
  }

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _handleCapture(String imageBase64) async {
    setState(() {
      _step = _FlowStep.processing;
      _processingMessage = 'Verifying proximity…';
      _error = null;
    });

    try {
      // 1. Fetch fresh BLE token as user clicks "mark present" (final confirm)
      // This solves the 30-second rotation issue.
      final found = await _bleService.scan(targetDeviceName: widget.deviceName);
      
      if (!found) {
        setState(() {
          _error = 'Could not verify classroom signal. Please stay near the device.';
          _step = _FlowStep.error;
        });
        return;
      }

      final bleToken = _bleService.bleToken;
      final deviceName = _bleService.deviceName;

      if (bleToken == null || bleToken.isEmpty) {
        setState(() {
          _error = 'Signal found but token extraction failed. Try again.';
          _step = _FlowStep.error;
        });
        return;
      }

      // 2. Proceed with backend verification using the FRESH token
      setState(() => _processingMessage = 'Recognizing face…');
      final data = await _apiService.verifyAndMark(
        sessionId: widget.sessionId,
        groupId: widget.groupId,
        imageBase64: imageBase64,
        bleToken: bleToken,
        deviceName: deviceName ?? widget.deviceName,
      );

      if (data['success'] == true) {
        final student = data['student'];
        setState(() {
          _matchedName = student?['name'];
          _matchedEnrollment = student?['enrollment_no'];
          _timestamp = data['timestamp'] ?? DateTime.now().toIso8601String();
          _step = _FlowStep.success;
        });
      } else {
        setState(() {
          _error = data['detail'] ?? data['message'] ?? 'Face not recognized.';
          _step = _FlowStep.error;
        });
      }
    } catch (e) {
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _step = _FlowStep.error;
      });
    }
  }

  void _handleMarkAnother() {
    setState(() {
      _step = _FlowStep.capture;
      _error = null;
      _matchedName = null;
      _matchedEnrollment = null;
      _timestamp = null;
      _processingMessage = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    // SUCCESS SCREEN
    if (_step == _FlowStep.success && _matchedName != null) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Success icon with ping
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        width: 96,
                        height: 96,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white.withValues(alpha: 0.1),
                        ),
                        child: const Icon(
                          Icons.check_circle,
                          size: 48,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),
                  Text(
                    "You're checked in",
                    style: GoogleFonts.inter(
                      fontSize: 28,
                      fontWeight: FontWeight.w300,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _matchedName!,
                    style: GoogleFonts.inter(
                      fontSize: 20,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _matchedEnrollment ?? '',
                    style: GoogleFonts.robotoMono(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 32),
                  if (_timestamp != null)
                    Text(
                      _formatTime(_timestamp!),
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: AppColors.textTertiary,
                        letterSpacing: 2,
                      ),
                    ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: GestureDetector(
                      onTap: () => Navigator.of(context).pop(),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(30),
                        ),
                        child: Center(
                          child: Text(
                            'Done',
                            style: GoogleFonts.inter(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: Colors.black,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  GestureDetector(
                    onTap: _handleMarkAnother,
                    child: Text(
                      'Mark Another',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    // ERROR SCREEN
    if (_step == _FlowStep.error) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.error.withValues(alpha: 0.1),
                      border: Border.all(
                        color: AppColors.error.withValues(alpha: 0.2),
                      ),
                    ),
                    child: Icon(
                      Icons.error_outline,
                      size: 40,
                      color: AppColors.error,
                    ),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'Verification Failed',
                    style: GoogleFonts.inter(
                      fontSize: 20,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _error ?? '',
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),
                  SizedBox(
                    width: double.infinity,
                    child: GestureDetector(
                      onTap: () {
                        setState(() {
                          _step = _FlowStep.capture;
                          _error = null;
                        });
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(30),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(
                              Icons.refresh,
                              size: 16,
                              color: Colors.black,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Try Again',
                              style: GoogleFonts.inter(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: Colors.black,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  GestureDetector(
                    onTap: () => Navigator.of(context).pop(),
                    child: Text(
                      'Cancel',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    // CAPTURE SCREEN
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          CameraWidget(
            onCapture: _handleCapture,
            isProcessing: _step == _FlowStep.processing,
            processingMessage: _processingMessage,
          ),
          // Back button
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 16,
            child: GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.black.withValues(alpha: 0.4),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.1),
                  ),
                ),
                child: const Icon(
                  Icons.arrow_back,
                  color: Colors.white,
                  size: 24,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final h = dt.hour > 12 ? dt.hour - 12 : dt.hour;
      final ampm = dt.hour >= 12 ? 'PM' : 'AM';
      return '${h == 0 ? 12 : h}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')} $ampm';
    } catch (_) {
      return '';
    }
  }
}
