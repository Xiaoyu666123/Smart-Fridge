import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/auth_store.dart';
import '../../core/theme.dart';
import 'features/user_management_page.dart';
import 'features/category_config_page.dart';
import 'features/logs_page.dart';
import 'features/usage_page.dart';
import 'features/waste_page.dart';
import 'features/perf_page.dart';
import 'features/lifecycle_page.dart';
import 'features/pending_labels_page.dart';
import 'features/agent_config_page.dart';
import 'features/batch_recognize_page.dart';
import 'features/screen_page.dart';
import 'features/workflow_page.dart';

/// 管理端"更多"：二级管理功能入口 + 退出。
class AdminMoreTab extends ConsumerWidget {
  const AdminMoreTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final adminName = ref.watch(authProvider).adminName;

    final groups = <(String, List<(IconData, String, Color, Widget)>)>[
      ('运营', [
        (Icons.tv, '可视化大屏', AppColors.brandPrimary, const ScreenPage()),
        (Icons.account_tree, '工作流', const Color(0xFF06B6D4),
            const WorkflowPage()),
        (Icons.center_focus_strong, '整柜批量识别', AppColors.info,
            const BatchRecognizePage()),
        (Icons.label, '标签缓冲', const Color(0xFF8B5CF6),
            const PendingLabelsPage()),
      ]),
      ('用户 & 配置', [
        (Icons.people, '用户管理', AppColors.brandPrimary,
            const UserManagementPage()),
        (Icons.tune, '品类配置', AppColors.info, const CategoryConfigPage()),
        (Icons.smart_toy, 'Agent 配置', const Color(0xFF8B5CF6),
            const AgentConfigPage()),
      ]),
      ('数据分析', [
        (Icons.delete_sweep, '浪费分析', AppColors.danger, const WastePage()),
        (Icons.token, 'Token 用量', AppColors.success, const UsagePage()),
        (Icons.speed, '性能监控', AppColors.warning, const PerfPage()),
        (Icons.timeline, '食材生命周期', AppColors.brandPrimary,
            const LifecyclePage()),
      ]),
      ('日志 & 审计', [
        (Icons.fact_check, '操作审计', AppColors.brandSecondary,
            const LogsPage(title: '操作审计', source: 'admin')),
        (Icons.receipt_long, '系统日志', AppColors.textSecondary,
            const LogsPage(title: '系统日志')),
      ]),
    ];

    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('更多'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppColors.brandSecondaryLight,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.admin_panel_settings,
                      color: AppColors.brandSecondary),
                ),
                const SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(adminName.isEmpty ? '管理员' : adminName,
                        style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 18,
                            fontWeight: FontWeight.w700)),
                    const Text('系统管理员',
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
                await ref.read(authProvider.notifier).logoutAdmin();
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
        ...items.map((it) => Container(
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.borderColor),
              ),
              child: ListTile(
                onTap: () => Navigator.of(context)
                    .push(MaterialPageRoute(builder: (_) => it.$4)),
                leading: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: it.$3.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(it.$1, color: it.$3, size: 20),
                ),
                title: Text(it.$2,
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w600)),
                trailing: const Icon(Icons.chevron_right,
                    color: AppColors.textPlaceholder),
              ),
            )),
        const SizedBox(height: 12),
      ],
    );
  }
}
