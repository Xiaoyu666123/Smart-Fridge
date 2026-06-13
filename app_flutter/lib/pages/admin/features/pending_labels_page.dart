import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/config.dart';
import '../../../core/dio_client.dart';
import '../../../api/admin_api.dart';

/// 标签缓冲：端侧 OCR 出的待关联标签。
class PendingLabelsPage extends ConsumerStatefulWidget {
  const PendingLabelsPage({super.key});

  @override
  ConsumerState<PendingLabelsPage> createState() => _PendingLabelsPageState();
}

class _PendingLabelsPageState extends ConsumerState<PendingLabelsPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _labels = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(adminApiProvider).pendingLabels();
      if (mounted) setState(() => _labels = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  ({Color color, String text}) _statusInfo(String s) {
    switch (s) {
      case 'consumed':
        return (color: AppColors.success, text: '已关联');
      case 'expired':
        return (color: AppColors.textPlaceholder, text: '已过期');
      default:
        return (color: AppColors.warning, text: '待关联');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('标签缓冲'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : _labels.isEmpty
              ? const Center(child: Text('暂无缓冲标签'))
              : RefreshIndicator(
                  onRefresh: _fetch,
                  color: AppColors.brandSecondary,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(14),
                    itemCount: _labels.length,
                    itemBuilder: (c, i) => _card(_labels[i]),
                  ),
                ),
    );
  }

  Widget _card(Map<String, dynamic> l) {
    final st = _statusInfo((l['status'] ?? 'pending').toString());
    final data = l['label_data'] as Map?;
    final brand = data?['brand']?.toString();
    final product = data?['product_name']?.toString();
    final expire = data?['expire_date']?.toString();
    final img = AppConfig.uploadUrl(l['label_image_path']?.toString());
    final text = (l['label_text'] ?? '').toString();

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (img.isNotEmpty)
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.network(img,
                  width: 56,
                  height: 56,
                  fit: BoxFit.cover,
                  errorBuilder: (c, e, s) => const SizedBox.shrink()),
            ),
          if (img.isNotEmpty) const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(product ?? brand ?? '未识别标签',
                          style: const TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: st.color.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(st.text,
                          style: TextStyle(fontSize: 11, color: st.color)),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                if (brand != null && brand.isNotEmpty)
                  Text('品牌：$brand',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textSecondary)),
                if (expire != null && expire.isNotEmpty)
                  Text('保质期：$expire',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textSecondary)),
                if ((brand == null || brand.isEmpty) &&
                    (expire == null || expire.isEmpty) &&
                    text.isNotEmpty)
                  Text(text,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
          IconButton(
            onPressed: () async {
              try {
                await ref
                    .read(adminApiProvider)
                    .deletePendingLabel(l['id'].toString());
                _fetch();
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text(extractError(e)),
                    backgroundColor: AppColors.danger,
                    behavior: SnackBarBehavior.floating,
                  ));
                }
              }
            },
            icon: const Icon(Icons.delete_outline,
                size: 20, color: AppColors.textPlaceholder),
          ),
        ],
      ),
    );
  }
}
