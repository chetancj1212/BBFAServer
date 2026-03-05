import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import '../../theme/app_theme.dart';
import 'package:google_fonts/google_fonts.dart';

class CameraWidget extends StatefulWidget {
  final void Function(String imageBase64) onCapture;
  final bool isProcessing;
  final String? processingMessage;

  const CameraWidget({
    super.key,
    required this.onCapture,
    this.isProcessing = false,
    this.processingMessage,
  });

  @override
  State<CameraWidget> createState() => _CameraWidgetState();
}

class _CameraWidgetState extends State<CameraWidget> {
  CameraController? _controller;
  bool _cameraReady = false;
  String? _cameraError;
  bool _captured = false;
  Uint8List? _capturedImageBytes;
  String? _capturedBase64;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    setState(() {
      _cameraError = null;
      _cameraReady = false;
    });

    try {
      final cameras = await availableCameras();
      // Prefer front camera
      final front = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );

      _controller = CameraController(
        front,
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await _controller!.initialize();
      if (mounted) {
        setState(() => _cameraReady = true);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _cameraError = 'Camera access denied. Check settings.');
      }
    }
  }

  Future<void> _handleCapture() async {
    if (_controller == null || !_cameraReady) return;

    try {
      final file = await _controller!.takePicture();
      final bytes = await file.readAsBytes();
      final base64 = base64Encode(bytes);

      setState(() {
        _captured = true;
        _capturedImageBytes = bytes;
        _capturedBase64 = base64;
      });
    } catch (e) {
      // Ignore capture errors
    }
  }

  void _handleRetake() {
    setState(() {
      _captured = false;
      _capturedImageBytes = null;
      _capturedBase64 = null;
    });
  }

  void _handleConfirm() {
    if (_capturedBase64 != null) {
      widget.onCapture(_capturedBase64!);
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black,
      child: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            // Camera card
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 400),
                decoration: BoxDecoration(
                  color: AppColors.surfacePrimary,
                  borderRadius: BorderRadius.circular(40),
                  border: Border.all(color: AppColors.borderPrimary),
                ),
                clipBehavior: Clip.antiAlias,
                child: AspectRatio(
                  aspectRatio: 3 / 4,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      // Camera preview or captured image
                      if (_captured && _capturedImageBytes != null)
                        ClipRRect(
                          borderRadius: BorderRadius.circular(40),
                          child: Image.memory(
                            _capturedImageBytes!,
                            fit: BoxFit.cover,
                          ),
                        )
                      else if (_cameraReady && _controller != null)
                        ClipRRect(
                          borderRadius: BorderRadius.circular(40),
                          child: OverflowBox(
                            alignment: Alignment.center,
                            // Let the preview use its native aspect ratio
                            // then crop to fill the 3:4 card without stretching
                            child: FittedBox(
                              fit: BoxFit.cover,
                              child: SizedBox(
                                width: 1,
                                height: _controller!.value.aspectRatio,
                                child: Transform.flip(
                                  flipX: true,
                                  child: CameraPreview(_controller!),
                                ),
                              ),
                            ),
                          ),
                        )
                      else if (_cameraError != null)
                        _buildErrorState()
                      else
                        _buildLoadingState(),

                      // Oval guide overlay
                      if (!_captured &&
                          !widget.isProcessing &&
                          _cameraReady)
                        Center(
                          child: Container(
                            width: MediaQuery.of(context).size.width * 0.45,
                            height: MediaQuery.of(context).size.width * 0.45 * 4 / 3,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(
                                MediaQuery.of(context).size.width * 0.225,
                              ),
                              border: Border.all(
                                color: Colors.white.withValues(alpha: 0.4),
                                width: 1,
                              ),
                            ),
                          ),
                        ),

                      // Instruction text
                      if (!_captured && !widget.isProcessing && _cameraReady)
                        Positioned(
                          top: 24,
                          left: 0,
                          right: 0,
                          child: Center(
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 16, vertical: 6),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.4),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(
                                  color: Colors.white.withValues(alpha: 0.1),
                                ),
                              ),
                              child: Text(
                                'Position face in oval',
                                style: GoogleFonts.inter(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                  color: Colors.white.withValues(alpha: 0.9),
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ),
                          ),
                        ),

                      // Processing overlay
                      if (widget.isProcessing)
                        Container(
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.4),
                            borderRadius: BorderRadius.circular(40),
                          ),
                          child: Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const CircularProgressIndicator(
                                  color: Colors.white,
                                  strokeWidth: 3,
                                ),
                                if (widget.processingMessage != null) ...[
                                  const SizedBox(height: 20),
                                  Text(
                                    widget.processingMessage!,
                                    style: GoogleFonts.inter(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w400,
                                      color: Colors.white.withValues(alpha: 0.9),
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),

            const SizedBox(height: 32),

            // Controls
            SizedBox(
              height: 80,
              child: _captured
                  ? Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Retake button
                        GestureDetector(
                          onTap: _handleRetake,
                          child: Container(
                            width: 64,
                            height: 64,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: AppColors.textTertiary,
                              ),
                            ),
                            child: const Icon(Icons.close,
                                color: AppColors.textTertiary, size: 24),
                          ),
                        ),
                        const SizedBox(width: 32),
                        // Confirm button
                        GestureDetector(
                          onTap: widget.isProcessing ? null : _handleConfirm,
                          child: Container(
                            width: 80,
                            height: 80,
                            decoration: const BoxDecoration(
                              shape: BoxShape.circle,
                              color: Colors.white,
                              boxShadow: [
                                BoxShadow(
                                  color: Color(0x1AFFFFFF),
                                  blurRadius: 20,
                                ),
                              ],
                            ),
                            child: Center(
                              child: widget.isProcessing
                                  ? const CircularProgressIndicator(
                                      color: Colors.black,
                                      strokeWidth: 3,
                                    )
                                  : const Icon(Icons.check,
                                      color: Colors.black, size: 40),
                            ),
                          ),
                        ),
                      ],
                    )
                  : Center(
                      // Shutter button
                      child: GestureDetector(
                        onTap: (!_cameraReady || widget.isProcessing)
                            ? null
                            : _handleCapture,
                        child: AnimatedOpacity(
                          opacity:
                              (!_cameraReady || widget.isProcessing) ? 0.5 : 1,
                          duration: const Duration(milliseconds: 200),
                          child: Container(
                            width: 80,
                            height: 80,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: Colors.white,
                                width: 2,
                              ),
                            ),
                            child: Center(
                              child: Container(
                                width: 68,
                                height: 68,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: Colors.transparent,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
            ),

            const Spacer(),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingState() {
    return Container(
      color: AppColors.surfacePrimary,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.camera_alt, size: 48, color: AppColors.textTertiary),
          const SizedBox(height: 12),
          Text(
            'Initializing camera...',
            style: GoogleFonts.inter(
              fontSize: 12,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Container(
      color: Colors.black,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            _cameraError!,
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppColors.error,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          GestureDetector(
            onTap: _initCamera,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.surfacePrimary,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                'Retry Camera',
                style: GoogleFonts.inter(
                  fontSize: 12,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
