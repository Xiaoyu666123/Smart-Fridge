import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/user_api.dart';

/// 健康饮食：营养结构分布 + 健康评分 + AI 教练建议。
class NutritionPage extends ConsumerStatefulWidget {
  const NutritionPage({super.key});

  @override
  ConsumerState<NutritionPage> createState() => _NutritionPageState();
}

class _NutritionPageState extends ConsumerState<NutritionPage> {
  bool _loading = true;
  Map<String, dynamic>? _report;
  Map<String, dynamic>? _coach;
  bool _coachLoading = false;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final r = await ref.read(userApiProvider).nutrition(days: 30);
      if (mounted) setState(() => _report = r);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadCoach() async {
    setState(() => _coachLoading = true);
    try {
      final c = await ref.read(userApiProvider).coach(days: 30);
      if (mounted) setState(() => _coach = c);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _coachLoading = false);
    }
  }

  Color _levelColor(String? level) {
    if (level == 'good') return AppColors.success;
    if (level == 'fair') return AppColors.warning;
    return AppColors.danger;
  }

  @override
  Widget build(BuildContext context) {
    final r = _report;
    final health = r?['health_overall'] as Map<String, dynamic>?;
    final score = (health?['score'] ?? 0) as num;
    final level = health?['level'] as String?;
    final tips = (health?['tips'] as List?)?.map((e) => e.toString()).toList() ?? [];
    final dist = (r?['distribution'] as List?) ?? [];

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('健康饮食')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : r == null
              ? const Center(child: Text('暂无数据'))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    // 评分卡
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: AppColors.bgCard,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: AppColors.borderColor),
                      ),
                      child: Row(
                        children: [
                          _scoreRing(score.toInt(), _levelColor(level)),
                          const SizedBox(width: 20),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  level == 'good'
                                      ? '饮食结构良好 👍'
                                      : level == 'fair'
                                          ? '饮食结构尚可'
                                          : '需要改善饮食 ⚠️',
                                  style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700),
                                ),
                                const SizedBox(height: 4),
                                Text('近 30 天 · 共 ${r['total'] ?? 0} 件食材',
                                    style: const TextStyle(
                                        fontSize: 12,
                                        color: AppColors.textSecondary)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    // 分布
                    if (dist.isNotEmpty) ...[
                      const Text('🥗 营养结构分布',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 10),
                      ...dist.map((d) => _distBar(Map<String, dynamic>.from(d),
                          (r['total'] ?? 1) as num)),
                      const SizedBox(height: 16),
                    ],
                    // 健康建议
                    if (tips.isNotEmpty) ...[
                      const Text('💡 改善建议',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      ...tips.map((t) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('· ',
                                    style: TextStyle(
                                        color: AppColors.brandPrimary)),
                                Expanded(
                                    child: Text(t,
                                        style: const TextStyle(
                                            fontSize: 13, height: 1.5))),
                              ],
                            ),
                          )),
                      const SizedBox(height: 16),
                    ],
                    // AI 教练
                    _coachSection(),
                  ],
                ),
    );
  }

  Widget _scoreRing(int score, Color color) {
    return SizedBox(
      width: 84,
      height: 84,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: 84,
            height: 84,
            child: CircularProgressIndicator(
              value: score / 100,
              strokeWidth: 8,
              backgroundColor: AppColors.bgSoft,
              valueColor: AlwaysStoppedAnimation(color),
            ),
          ),
          Text('$score',
              style: TextStyle(
                  fontSize: 26, fontWeight: FontWeight.w800, color: color)),
        ],
      ),
    );
  }

  Widget _distBar(Map<String, dynamic> d, num total) {
    final label = (d['label'] ?? d['tag'] ?? '').toString();
    final emoji = (d['emoji'] ?? '').toString();
    final count = (d['count'] ?? 0) as num;
    final colorStr = (d['color'] ?? '').toString();
    final ratio = total > 0 ? count / total : 0.0;
    Color barColor = AppColors.brandPrimary;
    if (colorStr.startsWith('#') && colorStr.length >= 7) {
      try {
        barColor = Color(int.parse('FF${colorStr.substring(1)}', radix: 16));
      } catch (_) {}
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('$emoji $label',
                  style: const TextStyle(fontSize: 13)),
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
              value: ratio.toDouble(),
              minHeight: 8,
              backgroundColor: AppColors.bgSoft,
              valueColor: AlwaysStoppedAnimation(barColor),
            ),
          ),
        ],
      ),
    );
  }

  Widget _coachSection() {
    final advice = _coach?['advice'] as Map<String, dynamic>?;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [
          AppColors.brandPrimary.withValues(alpha: 0.08),
          AppColors.brandPrimary.withValues(alpha: 0.02),
        ]),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.brandPrimaryLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🧑‍⚕️ AI 营养教练',
                  style:
                      TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
              const Spacer(),
              if (advice == null)
                TextButton(
                  onPressed: _coachLoading ? null : _loadCoach,
                  child: _coachLoading
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('获取建议'),
                ),
            ],
          ),
          if (advice != null) ...[
            const SizedBox(height: 6),
            Text((advice['summary'] ?? '').toString(),
                style: const TextStyle(fontSize: 14, height: 1.6)),
            const SizedBox(height: 12),
            _coachList('📋 本周计划', advice['week_plan']),
            _coachList('✅ 行动建议', advice['action_items']),
            _coachList('🚫 注意避免', advice['avoid']),
          ] else if (!_coachLoading)
            const Text('点击右上角，让 AI 根据你的饮食结构生成本周建议',
                style: TextStyle(
                    fontSize: 13, color: AppColors.textSecondary)),
        ],
      ),
    );
  }

  Widget _coachList(String title, dynamic items) {
    final list = (items as List?)?.map((e) => e.toString()).toList() ?? [];
    if (list.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          ...list.map((t) => Padding(
                padding: const EdgeInsets.only(bottom: 3, left: 4),
                child: Text('· $t',
                    style: const TextStyle(fontSize: 13, height: 1.5)),
              )),
        ],
      ),
    );
  }
}
