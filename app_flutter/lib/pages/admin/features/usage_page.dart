import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/admin_api.dart';

/// Token 用量统计。
class UsagePage extends ConsumerStatefulWidget {
  const UsagePage({super.key});

  @override
  ConsumerState<UsagePage> createState() => _UsagePageState();
}

class _UsagePageState extends ConsumerState<UsagePage> {
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
      final d = await ref.read(adminApiProvider).usageSummary(days: 30);
      if (mounted) setState(() => _data = d);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    final byEndpoint = (d?['by_endpoint'] as List?) ?? [];
    final byProvider = (d?['by_provider'] as List?) ?? [];
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('Token 用量'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : d == null
              ? const Center(child: Text('暂无数据'))
              : ListView(
                  padding: const EdgeInsets.all(14),
                  children: [
                    Row(
                      children: [
                        _stat('总调用', '${d['total_calls'] ?? 0}',
                            AppColors.brandPrimary),
                        _stat('失败', '${d['failed_calls'] ?? 0}',
                            AppColors.danger),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        _stat('Tokens', '${d['total_tokens'] ?? 0}',
                            AppColors.info),
                        _stat(
                            '成本',
                            '\$${((d['total_cost_usd'] ?? 0) as num).toStringAsFixed(3)}',
                            AppColors.success),
                      ],
                    ),
                    const SizedBox(height: 20),
                    if (byProvider.isNotEmpty) ...[
                      const Text('按服务商',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ...byProvider.map((p) => _listRow(
                          (p['provider'] ?? '').toString(),
                          '${p['calls']} 次 · ${p['tokens']} tokens')),
                      const SizedBox(height: 16),
                    ],
                    if (byEndpoint.isNotEmpty) ...[
                      const Text('按接口',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ...byEndpoint.map((p) => _listRow(
                          (p['endpoint'] ?? '').toString(),
                          '${p['calls']} 次 · ${p['tokens']} tokens')),
                    ],
                  ],
                ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.borderColor),
        ),
        child: Column(
          children: [
            Text(value,
                style: TextStyle(
                    fontSize: 22, fontWeight: FontWeight.w800, color: color)),
            const SizedBox(height: 4),
            Text(label,
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textSecondary)),
          ],
        ),
      ),
    );
  }

  Widget _listRow(String name, String sub) {
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
          Expanded(
              child: Text(name,
                  style: const TextStyle(fontWeight: FontWeight.w600))),
          Text(sub,
              style: const TextStyle(
                  fontSize: 12, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}
