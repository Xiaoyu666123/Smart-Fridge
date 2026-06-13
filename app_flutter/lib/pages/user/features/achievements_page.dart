import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/user_api.dart';

/// 我的成就：等级 + 个人档案 + 徽章墙。
class AchievementsPage extends ConsumerStatefulWidget {
  const AchievementsPage({super.key});

  @override
  ConsumerState<AchievementsPage> createState() => _AchievementsPageState();
}

class _AchievementsPageState extends ConsumerState<AchievementsPage> {
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
      final d = await ref.read(userApiProvider).achievements();
      if (mounted) setState(() => _data = d);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = _data?['profile'] as Map<String, dynamic>?;
    final badges = (_data?['achievements'] as List?) ?? [];

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('我的成就')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : profile == null
              ? const Center(child: Text('暂无数据'))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _levelCard(profile),
                    const SizedBox(height: 16),
                    _statsGrid(profile),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        const Text('🏅 徽章墙',
                            style: TextStyle(
                                fontSize: 15, fontWeight: FontWeight.w700)),
                        const SizedBox(width: 8),
                        Text(
                            '${profile['unlocked_count']}/${profile['total_count']}',
                            style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.textSecondary)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    GridView.count(
                      crossAxisCount: 3,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      mainAxisSpacing: 12,
                      crossAxisSpacing: 12,
                      childAspectRatio: 0.82,
                      children: badges
                          .map((b) => _badge(Map<String, dynamic>.from(b)))
                          .toList(),
                    ),
                  ],
                ),
    );
  }

  Widget _levelCard(Map<String, dynamic> p) {
    final score = (p['level_score'] ?? 0) as num;
    final next = (p['level_next_score'] ?? 1) as num;
    final ratio = next > 0 ? (score / next).clamp(0.0, 1.0) : 1.0;
    return Container(
      padding: const EdgeInsets.all(20),
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
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.brandSecondaryLight,
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: const Text('👑', style: TextStyle(fontSize: 24)),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Lv.${p['level_idx']} ${p['level_name']}',
                      style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 18,
                          fontWeight: FontWeight.w800)),
                  Text('${p['username']} · 已加入 ${p['register_days']} 天',
                      style: const TextStyle(
                          color: AppColors.textSecondary, fontSize: 12)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: ratio.toDouble(),
              minHeight: 8,
              backgroundColor: AppColors.bgSoft,
              valueColor: const AlwaysStoppedAnimation(AppColors.brandSecondary),
            ),
          ),
          const SizedBox(height: 4),
          Text('成长值 $score / $next',
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _statsGrid(Map<String, dynamic> p) {
    final stats = [
      ('${p['saved_count']}', '收藏食谱'),
      ('${p['total_cooks']}', '累计打卡'),
      ('${p['inv_consumed']}', '已消耗'),
      ('${p['inv_categories']}', '管理品类'),
    ];
    return Row(
      children: stats.map((s) {
        return Expanded(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 4),
            padding: const EdgeInsets.symmetric(vertical: 14),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: Column(
              children: [
                Text(s.$1,
                    style: const TextStyle(
                        fontSize: 20, fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
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

  Widget _badge(Map<String, dynamic> b) {
    final unlocked = b['unlocked'] == true;
    final emoji = (b['emoji'] ?? '🏅').toString();
    final name = (b['name'] ?? '').toString();
    final progress = (b['progress'] ?? 0) as num;
    final total = (b['total'] ?? 1) as num;
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: unlocked ? AppColors.brandPrimarySoft : AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
            color: unlocked
                ? AppColors.brandPrimaryLight
                : AppColors.borderColor),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Opacity(
            opacity: unlocked ? 1 : 0.3,
            child: Text(emoji, style: const TextStyle(fontSize: 30)),
          ),
          const SizedBox(height: 4),
          Text(name,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: unlocked
                      ? AppColors.textPrimary
                      : AppColors.textPlaceholder)),
          const SizedBox(height: 2),
          if (!unlocked)
            Text('$progress/$total',
                style: const TextStyle(
                    fontSize: 10, color: AppColors.textPlaceholder))
          else
            const Icon(Icons.check_circle,
                size: 14, color: AppColors.success),
        ],
      ),
    );
  }
}
