import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/theme.dart';
import '../../core/dio_client.dart';
import '../../api/user_api.dart';

/// 食材识别页：拍照 / 相册选图 → 调后端 VLM 识别 → 展示结果。
class RecognizeTab extends ConsumerStatefulWidget {
  const RecognizeTab({super.key});

  @override
  ConsumerState<RecognizeTab> createState() => _RecognizeTabState();
}

class _RecognizeTabState extends ConsumerState<RecognizeTab> {
  final _picker = ImagePicker();
  File? _image;
  bool _loading = false;
  Map<String, dynamic>? _result;
  String? _error;

  /// 上传大小上限：5MB（base64 后约 6.7MB，后端一般限制 10MB）
  static const _maxBytes = 5 * 1024 * 1024;

  Future<void> _pick(ImageSource source) async {
    try {
      final x = await _picker.pickImage(
        source: source,
        maxWidth: 1280,
        maxHeight: 1280,
        imageQuality: 80,
      );
      if (x == null) return;
      final file = File(x.path);

      // 检查文件大小，超过限制时进一步压缩
      final bytes = await file.readAsBytes();
      if (bytes.length > _maxBytes) {
        // 重新以更低质量压缩
        final x2 = await _picker.pickImage(
          source: source,
          maxWidth: 800,
          maxHeight: 800,
          imageQuality: 50,
        );
        if (x2 == null) return;
        final file2 = File(x2.path);
        final bytes2 = await file2.readAsBytes();
        if (bytes2.length > _maxBytes) {
          if (mounted) {
            setState(() => _error = '图片过大（${(bytes2.length / 1024 / 1024).toStringAsFixed(1)}MB），请使用更小的图片');
          }
          return;
        }
        await _doRecognize(file2, bytes2);
      } else {
        await _doRecognize(file, bytes);
      }
    } catch (e) {
      if (mounted) setState(() => _error = extractError(e, '识别失败，请重试'));
    }
  }

  Future<void> _doRecognize(File file, List<int> bytes) async {
    setState(() {
      _image = file;
      _result = null;
      _error = null;
      _loading = true;
    });
    try {
      final b64 = base64Encode(bytes);
      final res = await ref.read(userApiProvider).recognize(b64);
      if (mounted) setState(() => _result = res);
    } catch (e) {
      if (mounted) setState(() => _error = extractError(e, '识别失败，请重试'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('食材识别')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 图片预览区
          AspectRatio(
            aspectRatio: 4 / 3,
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderColor),
              ),
              clipBehavior: Clip.antiAlias,
              child: _image != null
                  ? Stack(
                      fit: StackFit.expand,
                      children: [
                        Image.file(_image!, fit: BoxFit.contain),
                        if (_loading)
                          Container(
                            color: Colors.black.withValues(alpha: 0.4),
                            child: const Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  CircularProgressIndicator(color: Colors.white),
                                  SizedBox(height: 12),
                                  Text('AI 识别中…',
                                      style: TextStyle(color: Colors.white)),
                                ],
                              ),
                            ),
                          ),
                      ],
                    )
                  : const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.add_a_photo_outlined,
                              size: 48, color: AppColors.textPlaceholder),
                          SizedBox(height: 12),
                          Text('拍照或从相册选择食材图片',
                              style: TextStyle(color: AppColors.textSecondary)),
                        ],
                      ),
                    ),
            ),
          ),
          const SizedBox(height: 16),
          // 操作按钮
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _loading ? null : () => _pick(ImageSource.camera),
                  icon: const Icon(Icons.camera_alt, size: 18),
                  label: const Text('拍照识别'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _loading ? null : () => _pick(ImageSource.gallery),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.brandPrimary,
                    side: const BorderSide(color: AppColors.brandPrimary),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.photo_library_outlined, size: 18),
                  label: const Text('相册选择'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          if (_error != null) _errorCard(),
          if (_result != null) _resultCard(),
        ],
      ),
    );
  }

  Widget _errorCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppColors.danger),
          const SizedBox(width: 10),
          Expanded(
              child: Text(_error!,
                  style: const TextStyle(color: Color(0xFFB91C1C)))),
        ],
      ),
    );
  }

  Widget _resultCard() {
    final r = _result!;
    final cat = (r['category'] ?? '未知').toString();
    final conf = ((r['confidence'] ?? 0) as num).toDouble();
    final shelf = r['shelf_life_days'];
    final advice = (r['storage_advice'] ?? '').toString();

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderColor),
        boxShadow: const [
          BoxShadow(color: Color(0x0F000000), blurRadius: 10, offset: Offset(0, 4)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.brandPrimaryLight,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.restaurant,
                    color: AppColors.brandPrimaryDark),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(cat,
                      style: const TextStyle(
                          fontSize: 20, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 2),
                  Text('置信度 ${(conf * 100).toStringAsFixed(0)}%',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textSecondary)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          _infoRow(Icons.schedule, '建议保质期',
              shelf != null ? '$shelf 天' : '未知'),
          const SizedBox(height: 12),
          _infoRow(Icons.lightbulb_outline, '存储建议',
              advice.isEmpty ? '暂无' : advice),
        ],
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: AppColors.brandPrimary),
        const SizedBox(width: 10),
        Text('$label：',
            style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textSecondary)),
        Expanded(
          child: Text(value,
              style: const TextStyle(fontSize: 14, height: 1.5)),
        ),
      ],
    );
  }
}
