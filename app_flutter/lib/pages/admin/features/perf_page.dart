import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/admin_api.dart';

/// 性能监控：各工具的 P50/P95/成功率。
class PerfPage extends ConsumerStatefulWidget {
  const PerfPage({super.key});

  @override
  ConsumerState<PerfPage> createState() => _PerfPageState();
}

class _PerfPageState extends ConsumerState<PerfPage> {
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
      final d = await ref.read(adminApiProvider).perfStats(hours: 24);
      if (mounted) setState(() => _data = d);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    final tools = (d?['tools'] as List?) ?? [];
    final totalSteps = d?['total_steps'] ?? 0;

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('性能监控'),
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
                      child: Text('近 24 小时共执行 $totalSteps 个工具步骤',
                          style: const TextStyle(
                              fontSize: 14, fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(height: 16),
                    if (tools.isEmpty)
                      const Center(
                          child: Padding(
                        padding: EdgeInsets.only(top: 40),
                        child: Text('暂无工具调用记录',
                            style: TextStyle(color: AppColors.textSecondary)),
                      ))
                    else
                      ...tools.map((t) => _toolCard(Map<String, dynamic>.from(t))),
                  ],
                ),
    );
  }

  Widget _toolCard(Map<String, dynamic> t) {
    final name = (t['tool_name'] ?? '').toString();
    final count = t['count'] ?? 0;
    final successRate = ((t['success_rate'] ?? 0) as num).toDouble();
    final avg = t['avg_ms'] ?? 0;
    final p50 = t['p50_ms'] ?? 0;
    final p95 = t['p95_ms'] ?? 0;

    final rateColor = successRate >= 0.95
        ? AppColors.success
        : successRate >= 0.8
            ? AppColors.warning
            : AppColors.danger;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(name,
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w700)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: rateColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text('成功率 ${(successRate * 100).toStringAsFixed(0)}%',
                    style: TextStyle(fontSize: 11, color: rateColor)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _metric('调用', '$count'),
              _metric('平均', '${avg}ms'),
              _metric('P50', '${p50}ms'),
              _metric('P95', '${p95}ms'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _metric(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: const TextStyle(
                  fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label,
              style: const TextStyle(
                  fontSize: 11, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}
