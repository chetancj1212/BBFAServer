import 'package:flutter/material.dart';
import '../models/active_class.dart';
import '../theme/app_theme.dart';
import 'mark_presence_screen.dart';
import 'face_registration_screen.dart';
import 'ble_gateway_screen.dart';
import 'package:google_fonts/google_fonts.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  void _handleNavigateToMarkPresence(
      BuildContext context, BleGatewayData? gateway) {
    if (gateway == null || gateway.activeClass == null) return;

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MarkPresenceScreen(
          sessionId: gateway.activeClass!.sessionId,
          groupId: gateway.activeClass!.groupId,
          deviceName: gateway.deviceName ?? '',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final gateway = BleGatewayData.of(context);
    final activeClass = gateway?.activeClass;
    final hasActiveClass = activeClass != null;

    return Scaffold(
      backgroundColor: AppColors.bgPrimary,
      body: SafeArea(
        child: Stack(
          children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  // Top bar — status indicator
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Text(
                        hasActiveClass
                            ? 'ROOM ${activeClass.roomNo ?? "N/A"}'.toUpperCase()
                            : 'NO ACTIVE SESSION',
                        style: GoogleFonts.inter(
                          fontSize: 10,
                          fontWeight: FontWeight.w300,
                          letterSpacing: 2,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),

                  // Main content — centered
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Brand
                        Text(
                          'Markin',
                          style: GoogleFonts.bricolageGrotesque(
                            fontSize: 48,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            letterSpacing: -0.5,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          width: 48,
                          height: 1,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [
                                Colors.transparent,
                                Colors.white.withValues(alpha: 0.5),
                                Colors.transparent,
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),

                        if (hasActiveClass) ...[
                          const SizedBox(height: 24),
                          Text(
                            activeClass.fullDisplayName,
                            textAlign: TextAlign.center,
                            style: GoogleFonts.inter(
                              fontSize: 16,
                              fontWeight: FontWeight.w400,
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],

                        if (!hasActiveClass) ...[
                          const SizedBox(height: 24),
                          Text(
                            'No active class for this room',
                            style: GoogleFonts.inter(
                              fontSize: 14,
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],

                        const SizedBox(height: 48),

                        // Primary action — Mark Present for XYZ
                        GestureDetector(
                          onTap: hasActiveClass
                              ? () => _handleNavigateToMarkPresence(context, gateway)
                              : null,
                          child: AnimatedOpacity(
                            opacity: hasActiveClass ? 1.0 : 0.3,
                            duration: const Duration(milliseconds: 300),
                            child: Container(
                              width: 280,
                              height: 280,
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(32),
                                border: Border.all(color: AppColors.borderPrimary),
                                color: AppColors.surfaceSecondary,
                              ),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(24),
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: Colors.black,
                                      border: Border.all(
                                        color: AppColors.borderPrimary,
                                      ),
                                    ),
                                    child: const Icon(
                                            Icons.camera_alt_outlined,
                                            size: 32,
                                            color: Colors.white,
                                          ),
                                  ),
                                  const SizedBox(height: 24),
                                  Text(
                                    hasActiveClass
                                        ? 'MARK PRESENT'
                                        : 'MARK ATTENDANCE',
                                    style: GoogleFonts.inter(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                      letterSpacing: 1,
                                      color: Colors.white,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Bottom — Register Face button
                  Padding(
                    padding: const EdgeInsets.only(bottom: 32),
                    child: GestureDetector(
                      onTap: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const FaceRegistrationScreen(),
                          ),
                        );
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 16,
                        ),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(30),
                          color: AppColors.surfaceSecondary,
                          border: Border.all(color: AppColors.borderPrimary),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.person_add_outlined,
                              size: 16,
                              color: AppColors.textSecondary,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Register New Face',
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                letterSpacing: 0.5,
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
