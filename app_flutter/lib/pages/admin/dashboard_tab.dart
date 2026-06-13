import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import '../../core/auth_store.dart';
import '../../core/inv_utils.dart';
import '../../api/admin_api.dart';
import 'features/screen_page.dart';

/// 管理端数据大盘：本地聚合库存 + 用量。
class DashboardTab extends ConsumerStatefulWidget {
  const DashboardTab({super.key});

  @override
  ConsumerState<DashboardTab> createState() => _DashboardTabState();
}

class _DashboardTabState extends ConsumerState<DashboardTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _inv = [];
  Map<String, dynamic>? _usage;
  List<Map<String, dynamic>> _devices = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    final api = ref.read(adminApiProvider);
    final r = await Future.wait([
      api.inventory().catchError((_) => <Map<String, dynamic>>[]),
      api.usageSummary(days: 30).then<Map<String, dynamic>?>((v) => v).catchError((_) => null),
      api.devices().catchError((_) => <Map<String, dynamic>>[]),
    ]);
    if (!mounted) return;
    setState(() {
      _inv = r[0] as List<Map<String, dynamic>>;
      _usage = r[1] as Map<String, dynamic>?;
      _devices = r[2] as List<Map<String, dynamic>>;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final adminName = ref.watch(authProvider).adminName;
    final inStock = _inv.where((i) => i['status'] == 'IN_STOCK').toList();
    final consumed = _inv.where((i) => i['status'] == 'CONSUMED').length;
    final expiring = inStock.where((i) => hasExpiry(i) && remainDays(i) <= 3).length;
    final onlineDevices =
        _devices.where((d) => d['live_status'] == 'online').length;

    // 品类分布
    final byCat = <String, int>{};
    for (final i in inStock) {
      final c = (i['category'] ?? '其他').toString();
      byCat[c] = (byCat[c] ?? 0) + 1;
    }
    final topCats = byCat.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('数据大盘'),
        actions: [
          IconButton(
            tooltip: '可视化大屏',
            icon: const Icon(Icons.tv),
            onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const ScreenPage())),
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : RefreshIndicator(
              onRefresh: _fetch,
              color: AppColors.brandSecondary,
              child: ListView(
                padding: const EdgeInsets.all(14),
                children: [
                  Text('欢迎，$adminName',
                      style: const TextStyle(
                          fontSize: 18, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 14),
                  // KPI 卡
                  GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    childAspectRatio: 1.7,
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    children: [
                      _kpi('在库食材', '${inStock.length}', Icons.inventory_2,
                          AppColors.brandPrimary),
                      _kpi('临期待处理', '$expiring', Icons.alarm,
                          AppColors.warning),
                      _kpi('已消耗', '$consumed', Icons.check_circle,
                          AppColors.success),
                      _kpi('在线设备', '$onlineDevices/${_devices.length}',
                          Icons.devices, AppColors.info),
                    ],
                  ),
                  const SizedBox(height: 18),
                  // 用量
                  if (_usage != null) _usageCard(),
                  const SizedBox(height: 18),
                  // 品类分布
                  if (topCats.isNotEmpty) ...[
                    const Text('📦 库存品类分布',
                        style: TextStyle(
                            fontSize: 15, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 10),
                    ...topCats.take(8).map((e) =>
                        _catBar(e.key, e.value, inStock.length)),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _kpi(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(value,
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.w800)),
                Text(label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _usageCard() {
    final u = _usage!;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🤖 近 30 天 AI 用量',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          Row(
            children: [
              _usageStat('调用次数', '${u['total_calls'] ?? 0}'),
              _usageStat('Tokens', '${u['total_tokens'] ?? 0}'),
              _usageStat(
                  '成本',
                  '\$${((u['total_cost_usd'] ?? 0) as num).toStringAsFixed(3)}'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _usageStat(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: const TextStyle(
                  fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(label,
              style: const TextStyle(
                  fontSize: 11, color: AppColors.textSecondary)),
        ],
      ),
    );
  }

  Widget _catBar(String cat, int count, int total) {
    final ratio = total > 0 ? count / total : 0.0;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(cat, style: const TextStyle(fontSize: 13)),
              const Spacer(),
              Text('$count 件',
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textSecondary)),
            ],
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 8,
              backgroundColor: AppColors.bgSoft,
              valueColor:
                  const AlwaysStoppedAnimation(AppColors.brandPrimary),
            ),
          ),
        ],
      ),
    );
  }
}
