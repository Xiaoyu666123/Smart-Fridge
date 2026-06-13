import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/auth_store.dart';
import '../../core/theme.dart';
import 'features/expiring_page.dart';
import 'features/fridge_map_page.dart';
import 'features/shopping_page.dart';
import 'features/recipes_page.dart';
import 'features/nutrition_page.dart';
import 'features/achievements_page.dart';
import 'features/environment_page.dart';
import 'features/preferences_page.dart';

/// “我的”聚合页（用户中心 + 其它功能入口 + 退出）。
class ProfileTab extends ConsumerWidget {
  const ProfileTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final initial =
        (auth.username.isNotEmpty ? auth.username[0] : '?').toUpperCase();

    final groups = <(String, List<(IconData, String, Color, Widget)>)>[
      ('食材管理', [
        (Icons.alarm, '临期处理', AppColors.warning, const ExpiringPage()),
        (Icons.grid_view, '冰箱视图', AppColors.brandPrimary, const FridgeMapPage()),
        (Icons.shopping_cart, '购物清单', AppColors.success, const ShoppingPage()),
      ]),
      ('健康 & 食谱', [
        (Icons.star, '我的食谱', const Color(0xFF8B5CF6), const RecipesPage()),
        (Icons.eco, '健康饮食', AppColors.danger, const NutritionPage()),
        (Icons.emoji_events, '我的成就', AppColors.brandSecondary,
            const AchievementsPage()),
      ]),
      ('其他', [
        (Icons.wb_sunny, '环境信息', const Color(0xFF06B6D4),
            const EnvironmentPage()),
        (Icons.settings, '偏好设置', AppColors.textSecondary,
            const PreferencesPage()),
      ]),
    ];

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('我的')),
      body: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          // 用户卡
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 26,
                  backgroundColor: AppColors.brandPrimaryLight,
                  child: Text(initial,
                      style: const TextStyle(
                          color: AppColors.brandPrimaryDark,
                          fontSize: 22,
                          fontWeight: FontWeight.w700)),
                ),
                const SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(auth.username.isEmpty ? '--' : auth.username,
                        style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 18,
                            fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    const Text('普通用户',
                        style: TextStyle(
                            color: AppColors.textSecondary, fontSize: 12)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          ...groups.map((g) => _group(context, g.$1, g.$2)),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () async {
                await ref.read(authProvider.notifier).logoutUser();
                if (context.mounted) context.go('/login');
              },
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.danger,
                side: const BorderSide(color: AppColors.danger),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              icon: const Icon(Icons.logout, size: 18),
              label: const Text('退出登录'),
            ),
          ),
          const SizedBox(height: 16),
          const Center(
            child: Text('智能冰箱 · v1.0',
                style: TextStyle(
                    color: AppColors.textPlaceholder, fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _group(BuildContext context, String title,
      List<(IconData, String, Color, Widget)> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8, top: 4),
          child: Text(title,
              style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPlaceholder)),
        ),
        GridView.count(
          crossAxisCount: 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 1.0,
          children: items.map((it) {
            return GestureDetector(
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => it.$4),
                );
              },
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.bgCard,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppColors.borderColor),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: it.$3.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(it.$1, color: it.$3, size: 22),
                    ),
                    const SizedBox(height: 8),
                    Text(it.$2, style: const TextStyle(fontSize: 12)),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}
