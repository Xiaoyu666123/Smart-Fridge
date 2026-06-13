import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/admin_api.dart';

/// 用户管理：列表 + 搜索 + 新建 + 重置密码 + 删除。
class UserManagementPage extends ConsumerStatefulWidget {
  const UserManagementPage({super.key});

  @override
  ConsumerState<UserManagementPage> createState() => _UserManagementPageState();
}

class _UserManagementPageState extends ConsumerState<UserManagementPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _users = [];
  String _search = '';

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(adminApiProvider).users(search: _search);
      if (mounted) setState(() => _users = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toast(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: error ? AppColors.danger : AppColors.success,
      behavior: SnackBarBehavior.floating,
    ));
  }

  Future<void> _create() async {
    final uCtrl = TextEditingController();
    final pCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('新建用户'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
                controller: uCtrl,
                decoration: const InputDecoration(labelText: '用户名')),
            const SizedBox(height: 10),
            TextField(
                controller: pCtrl,
                decoration: const InputDecoration(labelText: '初始密码')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('创建')),
        ],
      ),
    );
    if (ok == true) {
      try {
        await ref.read(adminApiProvider).createUser(
            uCtrl.text.trim(), pCtrl.text.trim());
        _toast('已创建');
        _fetch();
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    }
  }

  Future<void> _resetPwd(Map<String, dynamic> u) async {
    final ctrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text('重置 ${u['username']} 的密码'),
        content: TextField(
            controller: ctrl,
            decoration: const InputDecoration(labelText: '新密码')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('确定')),
        ],
      ),
    );
    if (ok == true && ctrl.text.trim().isNotEmpty) {
      try {
        await ref.read(adminApiProvider)
            .resetUserPassword(u['id'].toString(), ctrl.text.trim());
        _toast('密码已重置');
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> u) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('删除用户'),
        content: Text('确定删除「${u['username']}」？该用户的数据会一并清除。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('删除', style: TextStyle(color: AppColors.danger))),
        ],
      ),
    );
    if (ok == true) {
      try {
        await ref.read(adminApiProvider).deleteUser(u['id'].toString());
        _toast('已删除');
        _fetch();
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('用户管理'),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _create,
        backgroundColor: AppColors.brandPrimary,
        child: const Icon(Icons.person_add, color: Colors.white),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              onSubmitted: (v) {
                _search = v.trim();
                _fetch();
              },
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: '搜索用户名，回车搜索',
                isDense: true,
              ),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(
                        color: AppColors.brandSecondary))
                : _users.isEmpty
                    ? const Center(child: Text('暂无用户'))
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(12, 0, 12, 90),
                        itemCount: _users.length,
                        itemBuilder: (c, i) => _card(_users[i]),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _card(Map<String, dynamic> u) {
    final name = (u['username'] ?? '').toString();
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
          CircleAvatar(
            backgroundColor: AppColors.brandPrimaryLight,
            child: Text(name.isNotEmpty ? name[0].toUpperCase() : '?',
                style: const TextStyle(
                    color: AppColors.brandPrimaryDark,
                    fontWeight: FontWeight.w700)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(
                    '库存 ${u['inventory_count'] ?? 0} · 偏好 ${u['preference_count'] ?? 0} · 对话 ${u['conversation_count'] ?? 0}',
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
          IconButton(
            onPressed: () => _resetPwd(u),
            icon: const Icon(Icons.key, size: 20),
            tooltip: '重置密码',
          ),
          IconButton(
            onPressed: () => _delete(u),
            icon: const Icon(Icons.delete_outline,
                size: 20, color: AppColors.danger),
            tooltip: '删除',
          ),
        ],
      ),
    );
  }
}
