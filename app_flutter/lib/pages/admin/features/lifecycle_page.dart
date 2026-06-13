import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/admin_api.dart';

/// 食材生命周期：来源 → 品类 → 终态 的流向（移动端用分层列表表达 Sankey）。
class LifecyclePage extends ConsumerStatefulWidget {
  const LifecyclePage({super.key});

  @override
  ConsumerState<LifecyclePage> createState() => _LifecyclePageState();
}

class _LifecyclePageState extends ConsumerState<LifecyclePage> {
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
      final d = await ref.read(adminApiProvider).lifecycle(days: 30);
      if (mounted) setState(() => _data = d);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    final links = (d?['links'] as List?) ?? [];
    final total = (d?['total'] ?? 0) as num;

    // 按 source 聚合 link
    final maxVal = links.fold<num>(
        1, (m, l) => (l['value'] as num) > m ? l['value'] as num : m);

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('食材生命周期'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : d == null
              ? const Center(child: Text('暂无数据'))
              : ListView(
                  padding: const EdgeInsets.all(14),
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.bgCard,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: AppColors.borderColor),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.timeline,
                              color: AppColors.brandPrimary),
                          const SizedBox(width: 10),
                          Text('近 30 天共 $total 件食材的流转',
                              style: const TextStyle(
                                  fontSize: 14, fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text('流向明细（来源 → 品类 / 品类 → 终态）',
                        style: TextStyle(
                            fontSize: 15, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 10),
                    ...links.map((l) {
                      final m = Map<String, dynamic>.from(l);
                      final v = (m['value'] ?? 0) as num;
                      final ratio = maxVal > 0 ? v / maxVal : 0.0;
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Row(
                                    children: [
                                      Text((m['source'] ?? '').toString(),
                                          style: const TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.w600)),
                                      const Padding(
                                        padding: EdgeInsets.symmetric(
                                            horizontal: 6),
                                        child: Icon(Icons.arrow_forward,
                                            size: 14,
                                            color: AppColors.textPlaceholder),
                                      ),
                                      Text((m['target'] ?? '').toString(),
                                          style: const TextStyle(
                                              fontSize: 13,
                                              color: AppColors.textSecondary)),
                                    ],
                                  ),
                                ),
                                Text('$v',
                                    style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.brandPrimary)),
                              ],
                            ),
                            const SizedBox(height: 4),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: LinearProgressIndicator(
                                value: ratio.toDouble(),
                                minHeight: 6,
                                backgroundColor: AppColors.bgSoft,
                                valueColor: const AlwaysStoppedAnimation(
                                    AppColors.brandPrimary),
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ),
    );
  }
}
