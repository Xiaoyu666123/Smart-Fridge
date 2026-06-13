import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/config.dart';
import '../../../core/inv_utils.dart';
import '../../../api/user_api.dart';

/// 冰箱视图：把带 bbox 的食材按坐标摆在冰箱画面上。
class FridgeMapPage extends ConsumerStatefulWidget {
  const FridgeMapPage({super.key});

  @override
  ConsumerState<FridgeMapPage> createState() => _FridgeMapPageState();
}

class _FridgeMapPageState extends ConsumerState<FridgeMapPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];

  // 端侧画面坐标基准（与 Web 一致，bbox 以此为参考系归一化）
  static const double _refW = 640;
  static const double _refH = 480;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(userApiProvider).inventory();
      if (mounted) {
        setState(() => _items = list
            .where((it) =>
                it['bbox'] is List && (it['bbox'] as List).length >= 4)
            .toList());
      }
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('冰箱视图')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : _items.isEmpty
              ? _empty()
              : RefreshIndicator(
                  onRefresh: _fetch,
                  color: AppColors.brandPrimary,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Text('共 ${_items.length} 件已定位食材',
                          style: const TextStyle(
                              color: AppColors.textSecondary)),
                      const SizedBox(height: 12),
                      _fridgeCanvas(),
                      const SizedBox(height: 16),
                      const Text('食材清单',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ..._items.map(_listRow),
                    ],
                  ),
                ),
    );
  }

  Widget _empty() {
    return ListView(children: const [
      SizedBox(height: 120),
      Icon(Icons.kitchen_outlined, size: 64, color: AppColors.textPlaceholder),
      SizedBox(height: 12),
      Center(
          child: Text('暂无带位置信息的食材\n端侧识别后会显示在冰箱画面上',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary))),
    ]);
  }

  Widget _fridgeCanvas() {
    return AspectRatio(
      aspectRatio: _refW / _refH,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final w = constraints.maxWidth;
          final h = constraints.maxHeight;
          return Container(
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFE0F2FE), Color(0xFFBAE6FD)],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.brandPrimaryLight, width: 2),
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              children: _items.map((it) {
                final bbox = (it['bbox'] as List).map((e) => (e as num).toDouble()).toList();
                final x = bbox[0] / _refW * w;
                final y = bbox[1] / _refH * h;
                final bw = (bbox[2] / _refW * w).clamp(24.0, w);
                final bh = (bbox[3] / _refH * h).clamp(24.0, h);
                final d = remainDays(it);
                Color c = AppColors.brandPrimary;
                if (hasExpiry(it)) {
                  if (d < 0) {
                    c = AppColors.danger;
                  } else if (d <= 3) {
                    c = AppColors.warning;
                  }
                }
                return Positioned(
                  left: x,
                  top: y,
                  child: GestureDetector(
                    onTap: () => _showDetail(it),
                    child: Container(
                      width: bw,
                      height: bh,
                      decoration: BoxDecoration(
                        color: c.withValues(alpha: 0.18),
                        border: Border.all(color: c, width: 2),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Center(
                        child: Text(
                          (it['category'] ?? '').toString(),
                          textAlign: TextAlign.center,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              color: c),
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          );
        },
      ),
    );
  }

  Widget _listRow(Map<String, dynamic> it) {
    final cat = (it['category'] ?? '未知').toString();
    final d = remainDays(it);
    String sub = '位置已标记';
    Color c = AppColors.textSecondary;
    if (hasExpiry(it)) {
      if (d < 0) {
        sub = '已过期 ${-d} 天';
        c = AppColors.danger;
      } else if (d <= 3) {
        sub = '还剩 $d 天';
        c = AppColors.warning;
      } else {
        sub = '还剩 $d 天';
      }
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: ListTile(
        onTap: () => _showDetail(it),
        leading: const Icon(Icons.location_on, color: AppColors.brandPrimary),
        title: Text(cat, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(sub, style: TextStyle(color: c, fontSize: 12)),
      ),
    );
  }

  void _showDetail(Map<String, dynamic> it) {
    final snapshot = AppConfig.uploadUrl(it['snapshot_path']?.toString());
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (c) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text((it['category'] ?? '未知').toString(),
                style: const TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            if (snapshot.isNotEmpty)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(snapshot,
                    height: 180,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorBuilder: (c, e, s) => const SizedBox.shrink()),
              ),
            const SizedBox(height: 12),
            if (it['brand'] != null &&
                it['brand'].toString().isNotEmpty)
              _detailRow('品牌', it['brand'].toString()),
            if (hasExpiry(it))
              _detailRow('剩余',
                  remainDays(it) < 0 ? '已过期' : '${remainDays(it)} 天'),
            _detailRow('状态', (it['status'] ?? '').toString()),
          ],
        ),
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Text('$label：',
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 14)),
          Text(value, style: const TextStyle(fontSize: 14)),
        ],
      ),
    );
  }
}
