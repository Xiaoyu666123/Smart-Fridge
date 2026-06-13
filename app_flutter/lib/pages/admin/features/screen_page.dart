import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/inv_utils.dart';
import '../../../api/admin_api.dart';

/// 可视化大屏：深色指挥中心风格，自动轮询刷新。适合横屏展示。
class ScreenPage extends ConsumerStatefulWidget {
  const ScreenPage({super.key});

  @override
  ConsumerState<ScreenPage> createState() => _ScreenPageState();
}

class _ScreenPageState extends ConsumerState<ScreenPage> {
  static const _bg = Color(0xFF0A1628);
  static const _card = Color(0xFF13243B);
  static const _accent = Color(0xFF22D3EE);
  static const _accent2 = Color(0xFF818CF8);

  List<Map<String, dynamic>> _inv = [];
  List<Map<String, dynamic>> _devices = [];
  Map<String, dynamic>? _usage;
  List<Map<String, dynamic>> _events = [];
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    // 横屏 + 沉浸式
    SystemChrome.setPreferredOrientations(
        [DeviceOrientation.landscapeLeft, DeviceOrientation.landscapeRight]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _fetch();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _fetch());
  }

  @override
  void dispose() {
    _timer?.cancel();
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  Future<void> _fetch() async {
    final api = ref.read(adminApiProvider);
    final r = await Future.wait([
      api.inventory().catchError((_) => <Map<String, dynamic>>[]),
      api.devices().catchError((_) => <Map<String, dynamic>>[]),
      api.usageSummary(days: 30).then<Map<String, dynamic>?>((v) => v).catchError((_) => null),
      api.events().catchError((_) => <Map<String, dynamic>>[]),
    ]);
    if (!mounted) return;
    setState(() {
      _inv = r[0] as List<Map<String, dynamic>>;
      _devices = r[1] as List<Map<String, dynamic>>;
      _usage = r[2] as Map<String, dynamic>?;
      _events = r[3] as List<Map<String, dynamic>>;
    });
  }

  @override
  Widget build(BuildContext context) {
    final inStock = _inv.where((i) => i['status'] == 'IN_STOCK').toList();
    final consumed = _inv.where((i) => i['status'] == 'CONSUMED').length;
    final expiring =
        inStock.where((i) => hasExpiry(i) && remainDays(i) <= 3).length;
    final online = _devices.where((d) => d['live_status'] == 'online').length;

    final byCat = <String, int>{};
    for (final i in inStock) {
      final c = (i['category'] ?? '其他').toString();
      byCat[c] = (byCat[c] ?? 0) + 1;
    }
    final topCats = byCat.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 标题栏
              Row(
                children: [
                  const Icon(Icons.kitchen, color: _accent, size: 26),
                  const SizedBox(width: 10),
                  const Text('智能冰箱 · 实时监控大屏',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1)),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: _accent.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: const Row(children: [
                      Icon(Icons.circle, color: Color(0xFF22D3EE), size: 8),
                      SizedBox(width: 6),
                      Text('实时 · 每10秒刷新',
                          style: TextStyle(color: _accent, fontSize: 12)),
                    ]),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close, color: Colors.white54),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              // 主体：左 KPI/品类，右 设备/事件
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      flex: 3,
                      child: Column(
                        children: [
                          Row(
                            children: [
                              _kpi('在库食材', '${inStock.length}', _accent),
                              const SizedBox(width: 12),
                              _kpi('临期预警', '$expiring', const Color(0xFFFBBF24)),
                              const SizedBox(width: 12),
                              _kpi('已消耗', '$consumed', const Color(0xFF34D399)),
                              const SizedBox(width: 12),
                              _kpi('在线设备', '$online/${_devices.length}', _accent2),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Expanded(child: _catChart(topCats, inStock.length)),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: Column(
                        children: [
                          Expanded(child: _usagePanel()),
                          const SizedBox(height: 12),
                          Expanded(flex: 2, child: _eventsPanel()),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _kpi(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value,
                style: TextStyle(
                    color: color,
                    fontSize: 30,
                    fontWeight: FontWeight.w900,
                    height: 1)),
            const SizedBox(height: 6),
            Text(label,
                style: const TextStyle(color: Colors.white60, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _panel(String title, Widget child) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          Expanded(child: child),
        ],
      ),
    );
  }

  Widget _catChart(List<MapEntry<String, int>> cats, int total) {
    return _panel(
      '库存品类分布',
      cats.isEmpty
          ? const Center(
              child: Text('暂无数据', style: TextStyle(color: Colors.white38)))
          : ListView(
              children: cats.take(8).map((e) {
                final ratio = total > 0 ? e.value / total : 0.0;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        Text(e.key,
                            style: const TextStyle(
                                color: Colors.white70, fontSize: 13)),
                        const Spacer(),
                        Text('${e.value}',
                            style: const TextStyle(
                                color: _accent,
                                fontSize: 13,
                                fontWeight: FontWeight.w700)),
                      ]),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: ratio,
                          minHeight: 8,
                          backgroundColor: Colors.white10,
                          valueColor: const AlwaysStoppedAnimation(_accent),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
    );
  }

  Widget _usagePanel() {
    final u = _usage;
    return _panel(
      'AI 用量（30天）',
      u == null
          ? const Center(
              child: Text('—', style: TextStyle(color: Colors.white38)))
          : Column(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _usageRow('调用', '${u['total_calls'] ?? 0}'),
                _usageRow('Tokens', '${u['total_tokens'] ?? 0}'),
                _usageRow('成本',
                    '\$${((u['total_cost_usd'] ?? 0) as num).toStringAsFixed(2)}'),
              ],
            ),
    );
  }

  Widget _usageRow(String label, String value) {
    return Row(
      children: [
        Text(label, style: const TextStyle(color: Colors.white60, fontSize: 13)),
        const Spacer(),
        Text(value,
            style: const TextStyle(
                color: _accent2, fontSize: 18, fontWeight: FontWeight.w800)),
      ],
    );
  }

  Widget _eventsPanel() {
    return _panel(
      '最近事件流',
      _events.isEmpty
          ? const Center(
              child: Text('暂无事件', style: TextStyle(color: Colors.white38)))
          : ListView.builder(
              itemCount: _events.take(20).length,
              itemBuilder: (c, i) {
                final e = _events[i];
                final type = (e['event_type'] ?? '').toString();
                final time = (e['create_at'] ?? '').toString();
                final isIn = type.contains('IN');
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Icon(isIn ? Icons.arrow_downward : Icons.arrow_upward,
                          color: isIn
                              ? const Color(0xFF34D399)
                              : const Color(0xFFFBBF24),
                          size: 14),
                      const SizedBox(width: 8),
                      Text(type,
                          style: const TextStyle(
                              color: Colors.white70, fontSize: 12)),
                      const Spacer(),
                      Text(
                          time.length >= 19
                              ? time.substring(11, 19)
                              : time,
                          style: const TextStyle(
                              color: Colors.white38, fontSize: 11)),
                    ],
                  ),
                );
              },
            ),
    );
  }
}
