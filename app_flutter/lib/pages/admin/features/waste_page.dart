import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/admin_api.dart';

/// 浪费分析：浪费率 + Top 浪费/消耗 + 补货建议。
class WastePage extends ConsumerStatefulWidget {
  const WastePage({super.key});

  @override
  ConsumerState<WastePage> createState() => _WastePageState();
}

class _WastePageState extends ConsumerState<WastePage> {
  bool _loading = true;
  Map<String, dynamic>? _data;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final d = await ref.read(adminApiProvider).wasteAnalytics(days: 30);
      if (mounted) setState(() => _data = d);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    final wasteRate = ((d?['waste_rate'] ?? 0) as num).toDouble();
    final topWasted = (d?['top_wasted'] as List?) ?? [];
    final topConsumed = (d?['top_consumed'] as List?) ?? [];
    final restock = (d?['restock_suggestions'] as List?) ?? [];

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('浪费分析'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : d == null
              ? const Center(child: Text('暂无数据'))
              : ListView(
                  padding: const EdgeInsets.all(14),
                  children: [
                    // 浪费率卡
                    Container(
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: AppColors.bgCard,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.borderColor),
                      ),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 70,
                            height: 70,
                            child: Stack(
                              alignment: Alignment.center,
                              children: [
                                CircularProgressIndicator(
                                  value: wasteRate / 100,
                                  strokeWidth: 8,
                                  backgroundColor: AppColors.bgSoft,
                                  valueColor: AlwaysStoppedAnimation(
                                      wasteRate > 20
                                          ? AppColors.danger
                                          : AppColors.warning),
                                ),
                                Text('${wasteRate.toStringAsFixed(0)}%',
                                    style: const TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.w800)),
                              ],
                            ),
                          ),
                          const SizedBox(width: 18),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('近 30 天浪费率',
                                    style: TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w700)),
                                const SizedBox(height: 4),
                                Text(
                                    '浪费 ${d['wasted'] ?? 0} 件 · 估损 ¥${((d['wasted_value'] ?? 0) as num).toStringAsFixed(1)}',
                                    style: const TextStyle(
                                        fontSize: 12,
                                        color: AppColors.textSecondary)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    if (topWasted.isNotEmpty) ...[
                      const Text('🗑 最常浪费',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ...topWasted.map((w) => _row(
                          (w['category'] ?? '').toString(),
                          '${w['count']} 件',
                          AppColors.danger)),
                      const SizedBox(height: 16),
                    ],
                    if (topConsumed.isNotEmpty) ...[
                      const Text('✅ 最常消耗',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ...topConsumed.map((w) => _row(
                          (w['category'] ?? '').toString(),
                          '${w['count']} 件',
                          AppColors.success)),
                      const SizedBox(height: 16),
                    ],
                    if (restock.isNotEmpty) ...[
                      const Text('🛒 补货建议',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ...restock.map((s) => Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppColors.bgCard,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: AppColors.borderColor),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text((s['category'] ?? '').toString(),
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w600)),
                                const SizedBox(height: 2),
                                Text((s['reason'] ?? '').toString(),
                                    style: const TextStyle(
                                        fontSize: 12,
                                        color: AppColors.textSecondary)),
                              ],
                            ),
                          )),
                    ],
                  ],
                ),
    );
  }

  Widget _row(String name, String value, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Row(
        children: [
          Container(width: 8, height: 8,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 10),
          Expanded(
              child: Text(name,
                  style: const TextStyle(fontWeight: FontWeight.w600))),
          Text(value,
              style: TextStyle(color: color, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}
