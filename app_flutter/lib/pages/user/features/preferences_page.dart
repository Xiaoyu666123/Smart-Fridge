import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/user_api.dart';

/// 偏好设置：饮食偏好的增删（让 AI 更懂你）。
class PreferencesPage extends ConsumerStatefulWidget {
  const PreferencesPage({super.key});

  @override
  ConsumerState<PreferencesPage> createState() => _PreferencesPageState();
}

class _PreferencesPageState extends ConsumerState<PreferencesPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _prefs = [];

  // 按分类组织的快捷选项
  static const _groups = [
    (icon: '🍜', key: '口味', color: Color(0xFFC98A1E),
        options: ['清淡', '重口', '微辣', '中辣', '不吃辣']),
    (icon: '🚫', key: '忌口', color: Color(0xFFD2503F),
        options: ['不吃香菜', '不吃葱姜蒜', '不吃内脏', '不吃羊肉']),
    (icon: '🥗', key: '饮食', color: Color(0xFF2E9E6B),
        options: ['少油少盐', '低碳水', '高蛋白', '素食为主']),
    (icon: '⚠️', key: '过敏', color: Color(0xFF5566B5),
        options: ['海鲜过敏', '花生过敏', '乳糖不耐', '麸质过敏']),
  ];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(userApiProvider).preferences();
      if (mounted) setState(() => _prefs = list);
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

  bool _has(String key, String value) => _prefs.any(
      (p) => p['preference_key'] == key && p['preference_value'] == value);

  Future<void> _add(String key, String value) async {
    if (_has(key, value)) return;
    try {
      await ref.read(userApiProvider).addPreference(key, value);
      _fetch();
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _delete(Map<String, dynamic> p) async {
    try {
      await ref.read(userApiProvider).deletePreference(p['id'].toString());
      setState(() => _prefs.remove(p));
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _addCustom() async {
    final keyCtrl = TextEditingController();
    final valCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('添加偏好'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: keyCtrl,
              decoration: const InputDecoration(
                  labelText: '类型', hintText: '口味 / 忌口 / 过敏…'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: valCtrl,
              decoration:
                  const InputDecoration(labelText: '内容', hintText: '比如：不吃辣'),
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('添加')),
        ],
      ),
    );
    if (ok == true) {
      final k = keyCtrl.text.trim();
      final v = valCtrl.text.trim();
      if (k.isNotEmpty && v.isNotEmpty) _add(k, v);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('偏好设置'),
        actions: [
          TextButton.icon(
            onPressed: _addCustom,
            icon: const Icon(Icons.add, size: 18),
            label: const Text('自定义'),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                _bannerCard(),
                const SizedBox(height: 20),
                _myPrefsSection(),
                const SizedBox(height: 24),
                const Text('快捷添加',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                ..._groups.map(_presetGroup),
              ],
            ),
    );
  }

  // 顶部说明 banner
  Widget _bannerCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.brandPrimarySoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.brandPrimaryLight),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.brandPrimaryLight,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.favorite,
                color: AppColors.brandPrimaryDark, size: 22),
          ),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('个性化你的口味',
                    style: TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w700)),
                SizedBox(height: 2),
                Text('设置后，AI 推荐食谱会自动避开忌口、贴合口味',
                    style: TextStyle(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                        height: 1.4)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // 我的偏好
  Widget _myPrefsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text('我的偏好',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(width: 8),
            if (_prefs.isNotEmpty)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
                decoration: BoxDecoration(
                  color: AppColors.brandPrimaryLight,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text('${_prefs.length}',
                    style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.brandPrimaryDark,
                        fontWeight: FontWeight.w700)),
              ),
          ],
        ),
        const SizedBox(height: 10),
        if (_prefs.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 28),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: const Column(
              children: [
                Icon(Icons.spa_outlined,
                    size: 40, color: AppColors.textPlaceholder),
                SizedBox(height: 8),
                Text('还没有设置偏好',
                    style: TextStyle(color: AppColors.textSecondary)),
                SizedBox(height: 2),
                Text('从下方挑选，或点右上角自定义',
                    style: TextStyle(
                        fontSize: 12, color: AppColors.textPlaceholder)),
              ],
            ),
          )
        else
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.bgCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderColor),
            ),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _prefs.map((p) {
                return Container(
                  padding: const EdgeInsets.fromLTRB(12, 6, 6, 6),
                  decoration: BoxDecoration(
                    color: AppColors.brandPrimarySoft,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: AppColors.brandPrimaryLight),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                          '${p['preference_key']} · ${p['preference_value']}',
                          style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.brandPrimaryDark,
                              fontWeight: FontWeight.w500)),
                      const SizedBox(width: 4),
                      GestureDetector(
                        onTap: () => _delete(p),
                        child: Container(
                          width: 18,
                          height: 18,
                          decoration: BoxDecoration(
                            color: AppColors.brandPrimaryLight,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.close,
                              size: 12, color: AppColors.brandPrimaryDark),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
      ],
    );
  }

  // 分类快捷组
  Widget _presetGroup(
      ({String icon, String key, Color color, List<String> options}) g) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
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
              Text(g.icon, style: const TextStyle(fontSize: 16)),
              const SizedBox(width: 6),
              Text(g.key,
                  style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: g.color)),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: g.options.map((opt) {
              final added = _has(g.key, opt);
              return GestureDetector(
                onTap: added ? () {
                  final p = _prefs.firstWhere((e) =>
                      e['preference_key'] == g.key &&
                      e['preference_value'] == opt);
                  _delete(p);
                } : () => _add(g.key, opt),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: added
                        ? g.color.withValues(alpha: 0.12)
                        : AppColors.bgColor,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(
                        color: added ? g.color : AppColors.borderColor),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(added ? Icons.check_circle : Icons.add_circle_outline,
                          size: 15,
                          color: added ? g.color : AppColors.textPlaceholder),
                      const SizedBox(width: 5),
                      Text(opt,
                          style: TextStyle(
                              fontSize: 13,
                              fontWeight:
                                  added ? FontWeight.w600 : FontWeight.w400,
                              color: added ? g.color : AppColors.textSecondary)),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
