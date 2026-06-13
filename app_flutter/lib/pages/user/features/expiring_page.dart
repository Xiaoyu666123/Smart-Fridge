import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/inv_utils.dart';
import '../../../api/user_api.dart';

/// 临期处理：按剩余天数分组展示在库食材。
class ExpiringPage extends ConsumerStatefulWidget {
  const ExpiringPage({super.key});

  @override
  ConsumerState<ExpiringPage> createState() => _ExpiringPageState();
}

class _ExpiringPageState extends ConsumerState<ExpiringPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(userApiProvider).inventory(status: 'IN_STOCK');
      if (mounted) setState(() => _items = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // 分组
    final expired = <Map<String, dynamic>>[];
    final today = <Map<String, dynamic>>[];
    final soon = <Map<String, dynamic>>[];
    final week = <Map<String, dynamic>>[];
    for (final it in _items) {
      if (!hasExpiry(it)) continue;
      final d = remainDays(it);
      if (d < 0) {
        expired.add(it);
      } else if (d <= 1) {
        today.add(it);
      } else if (d <= 3) {
        soon.add(it);
      } else if (d <= 7) {
        week.add(it);
      }
    }

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('临期处理')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : RefreshIndicator(
              onRefresh: _fetch,
              color: AppColors.brandPrimary,
              child: (expired.isEmpty &&
                      today.isEmpty &&
                      soon.isEmpty &&
                      week.isEmpty)
                  ? ListView(children: const [
                      SizedBox(height: 140),
                      Icon(Icons.check_circle_outline,
                          size: 64, color: AppColors.success),
                      SizedBox(height: 12),
                      Center(
                          child: Text('太棒了，近期没有临期食材',
                              style: TextStyle(color: AppColors.textSecondary))),
                    ])
                  : ListView(
                      padding: const EdgeInsets.all(14),
                      children: [
                        _group('已过期', expired, AppColors.danger, '❌'),
                        _group('今明到期', today, AppColors.warning, '🔥'),
                        _group('3 天内', soon, const Color(0xFFEAB308), '⏰'),
                        _group('7 天内', week, AppColors.brandPrimary, '📅'),
                      ],
                    ),
            ),
    );
  }

  Widget _group(
      String title, List<Map<String, dynamic>> items, Color color, String emoji) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 8, top: 6),
          child: Row(
            children: [
              Text('$emoji  $title',
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w700)),
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                    color: color, borderRadius: BorderRadius.circular(999)),
                child: Text('${items.length}',
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w700)),
              ),
            ],
          ),
        ),
        ...items.map((it) => _row(it, color)),
        const SizedBox(height: 14),
      ],
    );
  }

  Widget _row(Map<String, dynamic> item, Color color) {
    final cat = (item['category'] ?? '未知').toString();
    final brand = item['brand']?.toString();
    final d = remainDays(item);
    String daysText;
    if (d < 0) {
      daysText = '已过期 ${-d} 天';
    } else if (d == 0) {
      daysText = '今天到期';
    } else {
      daysText = '还剩 $d 天';
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border(left: BorderSide(color: color, width: 3)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(cat,
                        style: const TextStyle(
                            fontSize: 15, fontWeight: FontWeight.w600)),
                    if (brand != null && brand.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppColors.brandPrimaryLight,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(brand,
                            style: const TextStyle(
                                fontSize: 11,
                                color: AppColors.brandPrimaryDark)),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(daysText,
                    style: TextStyle(
                        fontSize: 13,
                        color: color,
                        fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
