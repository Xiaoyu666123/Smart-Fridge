import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/user_api.dart';

/// 我的食谱：收藏列表 + 评分 + 打卡(做了) + 删除。
class RecipesPage extends ConsumerStatefulWidget {
  const RecipesPage({super.key});

  @override
  ConsumerState<RecipesPage> createState() => _RecipesPageState();
}

class _RecipesPageState extends ConsumerState<RecipesPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _recipes = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(userApiProvider).savedRecipes(limit: 100);
      if (mounted) setState(() => _recipes = list);
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

  Future<void> _cook(Map<String, dynamic> r) async {
    try {
      final res = await ref.read(userApiProvider).cookRecipe(r['id'].toString());
      final n = res['consumed_count'] ?? 0;
      _toast('打卡成功！消耗了 $n 件食材');
      _fetch();
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _rate(Map<String, dynamic> r) async {
    int rating = (r['rating'] ?? 0) as int;
    final result = await showDialog<int>(
      context: context,
      builder: (c) => StatefulBuilder(
        builder: (c, setS) => AlertDialog(
          title: Text('给「${r['name']}」评分'),
          content: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(5, (i) {
              return IconButton(
                onPressed: () => setS(() => rating = i + 1),
                icon: Icon(
                  i < rating ? Icons.star : Icons.star_border,
                  color: AppColors.warning,
                  size: 32,
                ),
              );
            }),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(c), child: const Text('取消')),
            TextButton(
                onPressed: () => Navigator.pop(c, rating),
                child: const Text('保存')),
          ],
        ),
      ),
    );
    if (result != null && result > 0) {
      try {
        await ref.read(userApiProvider).updateRecipeMeta(r['id'].toString(),
            rating: result);
        _fetch();
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> r) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('删除食谱'),
        content: Text('确定删除「${r['name']}」吗？'),
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
        await ref.read(userApiProvider).deleteRecipe(r['id'].toString());
        setState(() => _recipes.remove(r));
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('我的食谱')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : _recipes.isEmpty
              ? _empty()
              : RefreshIndicator(
                  onRefresh: _fetch,
                  color: AppColors.brandPrimary,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(14),
                    itemCount: _recipes.length,
                    itemBuilder: (c, i) => _card(_recipes[i]),
                  ),
                ),
    );
  }

  Widget _empty() {
    return ListView(children: const [
      SizedBox(height: 120),
      Icon(Icons.menu_book_outlined, size: 64, color: AppColors.textPlaceholder),
      SizedBox(height: 12),
      Center(
          child: Text('还没有收藏的食谱\n去 AI 食谱推荐里收藏喜欢的菜吧',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary))),
    ]);
  }

  Widget _card(Map<String, dynamic> r) {
    final name = (r['name'] ?? '').toString();
    final summary = (r['summary'] ?? '').toString();
    final cookedCount = (r['cooked_count'] ?? 0) as int;
    final rating = (r['rating'] ?? 0) as int;
    final tags = (r['tags'] as List?)?.map((e) => e.toString()).toList() ?? [];
    final ingredients = (r['ingredients'] as List?) ?? [];
    final steps = (r['steps'] as List?)?.map((e) => e.toString()).toList() ?? [];

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      clipBehavior: Clip.antiAlias,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
          title: Text(name,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (summary.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(summary,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12)),
                ),
              const SizedBox(height: 6),
              Row(
                children: [
                  if (rating > 0) ...[
                    ...List.generate(
                        rating,
                        (_) => const Icon(Icons.star,
                            size: 13, color: AppColors.warning)),
                    const SizedBox(width: 8),
                  ],
                  if (cookedCount > 0)
                    Text('做过 $cookedCount 次',
                        style: const TextStyle(
                            fontSize: 11, color: AppColors.textPlaceholder)),
                ],
              ),
            ],
          ),
          children: [
            if (tags.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: tags
                      .map((t) => Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppColors.brandPrimarySoft,
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(t,
                                style: const TextStyle(
                                    fontSize: 11,
                                    color: AppColors.brandPrimaryDark)),
                          ))
                      .toList(),
                ),
              ),
            if (ingredients.isNotEmpty) ...[
              const Align(
                  alignment: Alignment.centerLeft,
                  child: Text('🥬 食材',
                      style: TextStyle(fontWeight: FontWeight.w700))),
              const SizedBox(height: 4),
              ...ingredients.map((ing) {
                final m = Map<String, dynamic>.from(ing);
                return Align(
                  alignment: Alignment.centerLeft,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: Text(
                        '· ${m['name'] ?? ''}'
                        '${m['amount'] != null && m['amount'].toString().isNotEmpty ? '  ${m['amount']}' : ''}',
                        style: const TextStyle(
                            fontSize: 13, color: AppColors.textSecondary)),
                  ),
                );
              }),
              const SizedBox(height: 10),
            ],
            if (steps.isNotEmpty) ...[
              const Align(
                  alignment: Alignment.centerLeft,
                  child: Text('👨‍🍳 做法',
                      style: TextStyle(fontWeight: FontWeight.w700))),
              const SizedBox(height: 4),
              ...steps.asMap().entries.map((e) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${e.key + 1}. ',
                            style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                color: AppColors.brandPrimaryDark)),
                        Expanded(
                            child: Text(e.value,
                                style: const TextStyle(
                                    fontSize: 13, height: 1.5))),
                      ],
                    ),
                  )),
              const SizedBox(height: 10),
            ],
            // 操作
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _cook(r),
                    icon: const Icon(Icons.restaurant, size: 16),
                    label: const Text('做了这道'),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  onPressed: () => _rate(r),
                  child: const Icon(Icons.star_border, size: 18),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  onPressed: () => _delete(r),
                  style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.danger),
                  child: const Icon(Icons.delete_outline, size: 18),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
