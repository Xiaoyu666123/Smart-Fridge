import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/auth_store.dart';
import '../../core/inv_utils.dart';
import '../../core/theme.dart';
import '../../api/user_api.dart';

/// 用户首页 Dashboard（原生镜像 Web 的 Home.vue）。
class HomeTab extends ConsumerStatefulWidget {
  /// 切换到其它底部 Tab 的回调（index）。
  final void Function(int index)? onJumpTab;
  const HomeTab({super.key, this.onJumpTab});

  @override
  ConsumerState<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends ConsumerState<HomeTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];
  List<Map<String, dynamic>> _recipes = [];
  Map<String, dynamic>? _env;
  Map<String, dynamic>? _nutrition;
  int _unread = 0;
  Map<String, dynamic>? _tip;
  bool _tipLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchAll();
  }

  Future<void> _fetchAll() async {
    setState(() => _loading = true);
    final api = ref.read(userApiProvider);
    final results = await Future.wait([
      api.inventory(status: 'IN_STOCK').catchError((_) => <Map<String, dynamic>>[]),
      api.savedRecipes(limit: 8).catchError((_) => <Map<String, dynamic>>[]),
      api.environment().then<Map<String, dynamic>?>((v) => v).catchError((_) => null),
      api.nutrition(days: 7).then<Map<String, dynamic>?>((v) => v).catchError((_) => null),
      api.unreadCount().then<int>((v) => v).catchError((_) => 0),
    ]);
    if (!mounted) return;
    setState(() {
      _items = results[0] as List<Map<String, dynamic>>;
      _recipes = results[1] as List<Map<String, dynamic>>;
      _env = results[2] as Map<String, dynamic>?;
      _nutrition = results[3] as Map<String, dynamic>?;
      _unread = results[4] as int;
      _loading = false;
    });
    _loadTip();
  }

  Future<void> _loadTip({bool refresh = false}) async {
    setState(() => _tipLoading = true);
    try {
      final t = await ref.read(userApiProvider).dailyTip(refresh: refresh);
      if (mounted) setState(() => _tip = t);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _tipLoading = false);
    }
  }

  List<Map<String, dynamic>> get _expiring {
    final list = _items.where((it) => remainDays(it) <= 3).toList();
    list.sort((a, b) => remainDays(a).compareTo(remainDays(b)));
    return list;
  }

  String get _greeting {
    final h = DateTime.now().hour;
    if (h < 6) return '夜深了';
    if (h < 11) return '早上好';
    if (h < 14) return '中午好';
    if (h < 18) return '下午好';
    return '晚上好';
  }

  String get _timeEmoji {
    final h = DateTime.now().hour;
    if (h < 6) return '🌙';
    if (h < 11) return '🌅';
    if (h < 14) return '☀️';
    if (h < 18) return '🌤️';
    return '🌆';
  }

  @override
  Widget build(BuildContext context) {
    final username = ref.watch(authProvider).username;
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(
          children: [
            Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                color: AppColors.brandPrimary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.kitchen, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 10),
            const Text('智能冰箱'),
          ],
        ),
        actions: [
          if (_unread > 0)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Center(
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.brandPrimaryLight,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text('$_unread 条未读',
                      style: const TextStyle(
                          color: AppColors.brandPrimaryDark, fontSize: 11)),
                ),
              ),
            ),
          IconButton(
            onPressed: _fetchAll,
            icon: const Icon(Icons.refresh, size: 22),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _fetchAll,
        color: AppColors.brandPrimary,
        child: _loading
            ? ListView(children: const [
                SizedBox(height: 240),
                Center(
                    child: CircularProgressIndicator(
                        color: AppColors.brandPrimary)),
              ])
            : ListView(
                padding: const EdgeInsets.fromLTRB(14, 16, 14, 24),
                children: [
                  _heroCard(username),
                  const SizedBox(height: 14),
                  _tipCard(),
                  const SizedBox(height: 18),
                  if (_expiring.isNotEmpty) ...[
                    _sectionTitle('⏰ 临期食材', count: _expiring.length),
                    const SizedBox(height: 10),
                    ..._expiring.take(6).map(_expiringRow),
                    const SizedBox(height: 18),
                  ],
                  _sectionTitle('⚡ 快捷入口'),
                  const SizedBox(height: 10),
                  _quickGrid(),
                  const SizedBox(height: 18),
                  _statsRow(),
                ],
              ),
      ),
    );
  }

  // ---- Hero ----
  Widget _heroCard(String username) {
    final exp = _expiring;
    String emoji, title, desc;
    Color accent = AppColors.brandPrimary;
    if (exp.where((e) => remainDays(e) < 0).isNotEmpty) {
      final n = exp.where((e) => remainDays(e) < 0).length;
      accent = AppColors.danger;
      emoji = '⚠️';
      title = '有 $n 件食材已过期';
      desc = '建议立刻处理，避免浪费';
    } else if (exp.where((e) => remainDays(e) <= 1).isNotEmpty) {
      final n = exp.where((e) => remainDays(e) <= 1).length;
      accent = AppColors.warning;
      emoji = '🔥';
      title = '今明到期 $n 件，赶紧用掉';
      desc = '让 AI 推荐做菜方案？';
    } else if (exp.isNotEmpty) {
      accent = AppColors.warning;
      emoji = '⏰';
      title = '${exp.length} 件将在 3 天内过期';
      desc = '可以先做消耗计划';
    } else if (_items.isNotEmpty) {
      accent = AppColors.success;
      emoji = '🌱';
      title = '冰箱状态良好，共 ${_items.length} 件';
      desc = '没有临期压力，放心规划本周饮食';
    } else {
      emoji = '🛒';
      title = '冰箱里还没有食材';
      desc = '让端侧设备录入后，AI 才能帮你推荐';
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('$_timeEmoji  ', style: const TextStyle(fontSize: 15)),
              Text('$_greeting，$username',
                  style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 14,
                      fontWeight: FontWeight.w500)),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: Text(emoji, style: const TextStyle(fontSize: 22)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            height: 1.3)),
                    const SizedBox(height: 4),
                    Text(desc,
                        style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 13,
                            height: 1.5)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          // 天气 + 健康分（淡色 chip）
          Row(
            children: [
              if (_env != null) _weatherChip(),
              if (_env != null) const SizedBox(width: 10),
              if (_healthScore != null) _healthChip(),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => widget.onJumpTab?.call(3),
              icon: const Icon(Icons.auto_awesome, size: 18),
              label: Text(_expiring.isNotEmpty ? '让 AI 推荐做菜方案' : '和 AI 聊聊吃什么'),
            ),
          ),
        ],
      ),
    );
  }

  int? get _healthScore {
    final h = _nutrition?['health_overall'];
    if (h is Map && h['score'] != null) return (h['score'] as num).toInt();
    return null;
  }

  Widget _weatherChip() {
    final desc = (_env?['weather_desc'] ?? '').toString();
    final temp = _env?['temperature'];
    String em = '☀️';
    if (desc.contains('雨')) {
      em = '🌧';
    } else if (desc.contains('雪')) {
      em = '❄️';
    } else if (desc.contains('雾') || desc.contains('霾')) {
      em = '🌫';
    } else if (desc.contains('云')) {
      em = '⛅';
    } else if (desc.contains('阴')) {
      em = '☁️';
    } else if (desc.contains('晴')) {
      em = '☀️';
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
          color: AppColors.bgSoft,
          borderRadius: BorderRadius.circular(10)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(em, style: const TextStyle(fontSize: 20)),
        const SizedBox(width: 8),
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${temp ?? '--'}°',
              style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 15,
                  fontWeight: FontWeight.w700)),
          Text('$desc·${_env?['city'] ?? ''}',
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 10)),
        ]),
      ]),
    );
  }

  Widget _healthChip() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
          color: AppColors.bgSoft,
          borderRadius: BorderRadius.circular(10)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text('$_healthScore',
            style: const TextStyle(
                color: AppColors.brandPrimaryDark,
                fontSize: 17,
                fontWeight: FontWeight.w800)),
        const SizedBox(width: 6),
        const Text('饮食评分',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
      ]),
    );
  }

  // ---- AI 小贴士 ----
  Widget _tipCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.brandPrimarySoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.brandPrimaryLight),
      ),
      child: Row(
        children: [
          const Text('💡', style: TextStyle(fontSize: 26)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('AI 今日小贴士',
                    style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: AppColors.brandPrimaryDark)),
                const SizedBox(height: 4),
                Text(
                  _tip != null
                      ? (_tip!['tip'] ?? '').toString()
                      : (_tipLoading ? '正在生成…' : '点击刷新获取一条建议'),
                  style: const TextStyle(
                      fontSize: 14, color: AppColors.textPrimary, height: 1.5),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: _tipLoading ? null : () => _loadTip(refresh: true),
            icon: _tipLoading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.refresh, size: 18),
            color: AppColors.brandPrimaryDark,
          ),
        ],
      ),
    );
  }

  // ---- section title ----
  Widget _sectionTitle(String text, {int? count}) {
    return Row(
      children: [
        Text(text,
            style: const TextStyle(
                fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
        if (count != null) ...[
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
            decoration: BoxDecoration(
                color: AppColors.danger, borderRadius: BorderRadius.circular(999)),
            child: Text('$count',
                style: const TextStyle(
                    color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
          ),
        ],
      ],
    );
  }

  // ---- 临期行 ----
  Widget _expiringRow(Map<String, dynamic> item) {
    final d = remainDays(item);
    final cat = (item['category'] ?? '未知').toString();
    Color border;
    String emoji, daysText;
    if (d < 0) {
      border = AppColors.danger;
      emoji = '❌';
      daysText = '已过期 ${-d} 天';
    } else if (d <= 1) {
      border = AppColors.warning;
      emoji = '🔥';
      daysText = d == 0 ? '今天到期' : '还剩 1 天';
    } else {
      border = const Color(0xFFFADB14);
      emoji = '⏰';
      daysText = '还剩 $d 天';
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border(left: BorderSide(color: border, width: 3)),
        boxShadow: const [
          BoxShadow(color: Color(0x0F000000), blurRadius: 6, offset: Offset(0, 2)),
        ],
      ),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 20)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(cat,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(daysText,
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
          TextButton(
            onPressed: () => widget.onJumpTab?.call(1), // 跳库存
            child: const Text('查看'),
          ),
        ],
      ),
    );
  }

  // ---- 快捷入口宫格 ----
  Widget _quickGrid() {
    final entries = [
      ('💬', 'AI 食谱', 3),
      ('🥬', '库存查看', 1),
      ('📷', '食材识别', 2),
      ('👤', '我的', 4),
    ];
    return Row(
      children: entries.map((e) {
        return Expanded(
          child: GestureDetector(
            onTap: () => widget.onJumpTab?.call(e.$3),
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.symmetric(vertical: 16),
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.borderColor),
              ),
              child: Column(
                children: [
                  Text(e.$1, style: const TextStyle(fontSize: 26)),
                  const SizedBox(height: 6),
                  Text(e.$2,
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600)),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  // ---- 统计 ----
  Widget _statsRow() {
    final totalExpiring = _expiring.length;
    final cooks = _recipes.fold<int>(
        0, (s, r) => s + ((r['cooked_count'] ?? 0) as num).toInt());
    final stats = [
      ('${_items.length}', '在库食材'),
      ('$totalExpiring', '临期待处理'),
      ('${_recipes.length}', '收藏食谱'),
      ('$cooks', '累计打卡'),
    ];
    return Row(
      children: stats.map((s) {
        return Expanded(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 4),
            padding: const EdgeInsets.symmetric(vertical: 16),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: Column(
              children: [
                Text(s.$1,
                    style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary)),
                const SizedBox(height: 4),
                Text(s.$2,
                    style: const TextStyle(
                        fontSize: 11, color: AppColors.textSecondary)),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}
