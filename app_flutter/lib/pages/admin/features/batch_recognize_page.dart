import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/admin_api.dart';

/// 整柜批量识别：拍照 → 检测多个食材 → 勾选 → 批量入库。
class BatchRecognizePage extends ConsumerStatefulWidget {
  const BatchRecognizePage({super.key});

  @override
  ConsumerState<BatchRecognizePage> createState() =>
      _BatchRecognizePageState();
}

class _BatchRecognizePageState extends ConsumerState<BatchRecognizePage> {
  final _picker = ImagePicker();
  File? _image;
  bool _loading = false;
  List<Map<String, dynamic>> _items = [];
  final Set<int> _selected = {};

  Future<void> _pick(ImageSource source) async {
    try {
      final x = await _picker.pickImage(
          source: source, maxWidth: 1600, imageQuality: 85);
      if (x == null) return;
      setState(() {
        _image = File(x.path);
        _items = [];
        _selected.clear();
        _loading = true;
      });
      final bytes = await File(x.path).readAsBytes();
      final b64 = base64Encode(bytes);
      final items = await ref.read(adminApiProvider).detect(b64);
      if (mounted) {
        setState(() {
          _items = items;
          _selected.addAll(List.generate(items.length, (i) => i));
        });
      }
    } catch (e) {
      _toast(extractError(e, '识别失败'), error: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toast(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: error ? AppColors.danger : AppColors.success,
      behavior: SnackBarBehavior.floating,
    ));
  }

  Future<void> _bulkCreate() async {
    if (_selected.isEmpty) return;
    final payload = _selected.map((i) {
      final it = _items[i];
      return {
        'category': it['category'],
        'confidence': it['confidence'],
        'bbox': it['bbox'],
      };
    }).toList();
    setState(() => _loading = true);
    try {
      final res =
          await ref.read(adminApiProvider).bulkCreate('luckfox', payload);
      final n = res['created_count'] ?? 0;
      final skipped = res['skipped_count'] ?? 0;
      _toast('已入库 $n 件${skipped > 0 ? '，跳过重复 $skipped 件' : ''}');
      setState(() {
        _items = [];
        _selected.clear();
        _image = null;
      });
    } catch (e) {
      _toast(extractError(e), error: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('整柜批量识别'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
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
                  ? Stack(fit: StackFit.expand, children: [
                      Image.file(_image!, fit: BoxFit.contain),
                      if (_loading)
                        Container(
                          color: Colors.black.withValues(alpha: 0.4),
                          child: const Center(
                              child: CircularProgressIndicator(
                                  color: Colors.white)),
                        ),
                    ])
                  : const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.photo_camera_back_outlined,
                              size: 48, color: AppColors.textPlaceholder),
                          SizedBox(height: 12),
                          Text('拍整柜照片，AI 一次识别多个食材',
                              style:
                                  TextStyle(color: AppColors.textSecondary)),
                        ],
                      ),
                    ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _loading ? null : () => _pick(ImageSource.camera),
                  style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.brandSecondary),
                  icon: const Icon(Icons.camera_alt, size: 18),
                  label: const Text('拍照'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _loading ? null : () => _pick(ImageSource.gallery),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.brandSecondary,
                    side: const BorderSide(color: AppColors.brandSecondary),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.photo_library_outlined, size: 18),
                  label: const Text('相册'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (_items.isNotEmpty) ...[
            Row(
              children: [
                Text('识别到 ${_items.length} 个，已选 ${_selected.length}',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
                const Spacer(),
                TextButton(
                  onPressed: () => setState(() {
                    if (_selected.length == _items.length) {
                      _selected.clear();
                    } else {
                      _selected
                        ..clear()
                        ..addAll(List.generate(_items.length, (i) => i));
                    }
                  }),
                  child: Text(_selected.length == _items.length ? '取消全选' : '全选'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ..._items.asMap().entries.map((e) => _itemRow(e.key, e.value)),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed:
                    (_loading || _selected.isEmpty) ? null : _bulkCreate,
                style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.brandSecondary,
                    padding: const EdgeInsets.symmetric(vertical: 14)),
                icon: const Icon(Icons.save, size: 18),
                label: Text('批量入库（${_selected.length}）'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _itemRow(int i, Map<String, dynamic> it) {
    final sel = _selected.contains(i);
    final cat = (it['category'] ?? '').toString();
    final conf = ((it['confidence'] ?? 0) as num).toDouble();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
            color: sel ? AppColors.brandSecondary : AppColors.borderColor),
      ),
      child: CheckboxListTile(
        value: sel,
        activeColor: AppColors.brandSecondary,
        onChanged: (v) => setState(() {
          if (v == true) {
            _selected.add(i);
          } else {
            _selected.remove(i);
          }
        }),
        title: Text(cat, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('置信度 ${(conf * 100).toStringAsFixed(0)}%',
            style: const TextStyle(fontSize: 12)),
      ),
    );
  }
}
