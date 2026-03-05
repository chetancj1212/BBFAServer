import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/group.dart';
import '../models/student.dart';
import '../theme/app_theme.dart';
import 'widgets/camera_widget.dart';
import 'package:google_fonts/google_fonts.dart';

class FaceRegistrationScreen extends StatefulWidget {
  const FaceRegistrationScreen({super.key});

  @override
  State<FaceRegistrationScreen> createState() =>
      _FaceRegistrationScreenState();
}

enum _FaceRegStep { group, enrollment, capture, success }

class _FaceRegistrationScreenState extends State<FaceRegistrationScreen> {
  final ApiService _apiService = ApiService();

  _FaceRegStep _step = _FaceRegStep.group;
  List<Group> _groups = [];
  String _selectedGroupId = '';
  String _enrollmentNo = '';
  StudentLookup? _student;
  bool _isLoading = false;
  bool _isLoadingGroups = true;
  bool _isProcessing = false;
  String? _error;
  bool _isReRegistration = false;

  @override
  void initState() {
    super.initState();
    _fetchGroups();
  }

  Future<void> _fetchGroups() async {
    try {
      final groups = await _apiService.getGroups();
      if (mounted) {
        setState(() {
          _groups = groups;
          if (groups.isNotEmpty) _selectedGroupId = groups.first.id;
          _isLoadingGroups = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString().replaceFirst('Exception: ', '');
          _isLoadingGroups = false;
        });
      }
    }
  }

  Future<void> _handleLookup() async {
    if (_enrollmentNo.trim().isEmpty) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await _apiService.lookupStudent(
          _selectedGroupId, _enrollmentNo.trim());

      if (data['found'] == true && data['student'] != null) {
        final s = StudentLookup.fromJson(data['student']);
        setState(() {
          _student = s;
          _isReRegistration = s.hasFace == true;
          _step = _FaceRegStep.capture;
        });
      } else {
        setState(() => _error = 'Student not found.');
      }
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _handleCapture(String imageBase64) async {
    if (_student == null) return;

    setState(() {
      _isProcessing = true;
      _error = null;
    });

    try {
      final data = await _apiService.registerFace(
        enrollmentNo: _enrollmentNo.trim(),
        groupId: _selectedGroupId,
        imageBase64: imageBase64,
      );

      if (data['success'] == true) {
        setState(() => _step = _FaceRegStep.success);
      } else {
        setState(() {
          _error = data['message'] ?? 'Registration failed.';
          _isProcessing = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _isProcessing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // SUCCESS SCREEN
    if (_step == _FaceRegStep.success && _student != null) {
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
                      color: Colors.white.withValues(alpha: 0.1),
                    ),
                    child: const Icon(Icons.check_circle,
                        size: 40, color: Colors.white),
                  ),
                  const SizedBox(height: 32),
                  Text(
                    _isReRegistration ? 'Face Updated' : 'Registration Complete',
                    style: GoogleFonts.inter(
                      fontSize: 28,
                      fontWeight: FontWeight.w300,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _student!.name,
                    style: GoogleFonts.inter(
                      fontSize: 20,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _student!.enrollmentNo,
                    style: GoogleFonts.robotoMono(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 32),
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
                            'Back to Portal',
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
                ],
              ),
            ),
          ),
        ),
      );
    }

    // WIZARD
    return Scaffold(
      backgroundColor: AppColors.bgPrimary,
      body: SafeArea(
        child: Column(
          children: [
            // Header with back and progress
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  GestureDetector(
                    onTap: () {
                      if (_step == _FaceRegStep.enrollment) {
                        setState(() => _step = _FaceRegStep.group);
                      } else if (_step == _FaceRegStep.capture) {
                        setState(() => _step = _FaceRegStep.enrollment);
                      } else {
                        Navigator.of(context).pop();
                      }
                    },
                    child: const Padding(
                      padding: EdgeInsets.all(8),
                      child: Icon(Icons.arrow_back,
                          color: Colors.white60, size: 24),
                    ),
                  ),
                  // Progress dots
                  Row(
                    children: [1, 2, 3].map((i) {
                      final isActive =
                          (_step == _FaceRegStep.group && i == 1) ||
                              (_step == _FaceRegStep.enrollment && i <= 2) ||
                              (_step == _FaceRegStep.capture && i <= 3);
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        width: isActive ? 32 : 8,
                        height: 4,
                        margin: const EdgeInsets.symmetric(horizontal: 2),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(2),
                          color: isActive
                              ? Colors.white
                              : Colors.white.withValues(alpha: 0.2),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),

            // Main content
            Expanded(
              child: _step == _FaceRegStep.capture
                  ? _buildCaptureStep()
                  : Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: _step == _FaceRegStep.group
                          ? _buildGroupStep()
                          : _buildEnrollmentStep(),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGroupStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(),
        Text(
          'Select Class',
          style: GoogleFonts.inter(
            fontSize: 28,
            fontWeight: FontWeight.w300,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Choose your cohort',
          style: GoogleFonts.inter(
            fontSize: 14,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 32),
        Expanded(
          flex: 3,
          child: _isLoadingGroups
              ? const Center(
                  child: CircularProgressIndicator(
                      color: Colors.white, strokeWidth: 2))
              : ListView.separated(
                  itemCount: _groups.length,
                  separatorBuilder: (_, index) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final group = _groups[index];
                    final isSelected = group.id == _selectedGroupId;
                    return GestureDetector(
                      onTap: () =>
                          setState(() => _selectedGroupId = group.id),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          color: isSelected
                              ? Colors.white
                              : Colors.white.withValues(alpha: 0.05),
                          border: Border.all(
                            color: isSelected
                                ? Colors.transparent
                                : Colors.white.withValues(alpha: 0.1),
                          ),
                        ),
                        child: Text(
                          group.name,
                          style: GoogleFonts.inter(
                            fontSize: 18,
                            fontWeight: FontWeight.w500,
                            color: isSelected ? Colors.black : Colors.white60,
                          ),
                        ),
                      ),
                    );
                  },
                ),
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: GestureDetector(
            onTap: _selectedGroupId.isEmpty
                ? null
                : () => setState(() => _step = _FaceRegStep.enrollment),
            child: AnimatedOpacity(
              opacity: _selectedGroupId.isEmpty ? 0.3 : 1.0,
              duration: const Duration(milliseconds: 200),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Center(
                  child: Text(
                    'Continue',
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
        ),
        const Spacer(),
      ],
    );
  }

  Widget _buildEnrollmentStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Spacer(),
        Text(
          'Your ID',
          style: GoogleFonts.inter(
            fontSize: 28,
            fontWeight: FontWeight.w300,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Enter enrollment number',
          style: GoogleFonts.inter(
            fontSize: 14,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 48),
        TextField(
          autofocus: true,
          onChanged: (v) {
            setState(() {
              _enrollmentNo = v;
              _error = null;
            });
          },
          onSubmitted: (_) => _handleLookup(),
          style: GoogleFonts.robotoMono(
            fontSize: 36,
            fontWeight: FontWeight.w300,
            color: Colors.white,
          ),
          textAlign: TextAlign.center,
          decoration: InputDecoration(
            hintText: 'e.g. 2024001',
            hintStyle: GoogleFonts.robotoMono(
              fontSize: 36,
              fontWeight: FontWeight.w300,
              color: Colors.white.withValues(alpha: 0.1),
            ),
            filled: false,
            border: UnderlineInputBorder(
              borderSide:
                  BorderSide(color: Colors.white.withValues(alpha: 0.2), width: 2),
            ),
            enabledBorder: UnderlineInputBorder(
              borderSide:
                  BorderSide(color: Colors.white.withValues(alpha: 0.2), width: 2),
            ),
            focusedBorder: const UnderlineInputBorder(
              borderSide: BorderSide(color: Colors.white, width: 2),
            ),
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 16),
          Center(
            child: Text(
              _error!,
              style: GoogleFonts.inter(
                fontSize: 14,
                color: AppColors.error,
              ),
            ),
          ),
        ],
        const SizedBox(height: 48),
        SizedBox(
          width: double.infinity,
          child: GestureDetector(
            onTap: (_isLoading || _enrollmentNo.isEmpty)
                ? null
                : _handleLookup,
            child: AnimatedOpacity(
              opacity: (_isLoading || _enrollmentNo.isEmpty) ? 0.3 : 1.0,
              duration: const Duration(milliseconds: 200),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (_isLoading) ...[
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          color: Colors.black,
                          strokeWidth: 2,
                        ),
                      ),
                      const SizedBox(width: 8),
                    ],
                    Text(
                      _isLoading ? 'Verifying...' : 'Continue',
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
        ),
        const Spacer(flex: 2),
      ],
    );
  }

  Widget _buildCaptureStep() {
    return Stack(
      children: [
        CameraWidget(
          onCapture: _handleCapture,
          isProcessing: _isProcessing,
        ),
        // Student info overlay
        if (_student != null)
          Positioned(
            top: 8,
            right: 16,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.1),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _student!.name,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                  Text(
                    _student!.enrollmentNo,
                    style: GoogleFonts.robotoMono(
                      fontSize: 12,
                      color: Colors.white60,
                    ),
                  ),
                ],
              ),
            ),
          ),
        // Error overlay
        if (_error != null)
          Positioned(
            top: 80,
            left: 24,
            right: 24,
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.9),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _error!,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: Colors.white,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ),
      ],
    );
  }
}
