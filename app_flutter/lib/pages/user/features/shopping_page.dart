import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/user_api.dart';

/// 购物清单：勾选 / 添加 / 删除 / AI 建议 / 清除已购。
class ShoppingPage extends ConsumerStatefulWidget {
  const ShoppingPage({super.key});

  @override
  ConsumerState<ShoppingPage> createState() => _ShoppingPageState();
}

class _ShoppingPageState extends ConsumerState<ShoppingPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final res = await ref.read(userApiProvider).shoppingList();
      if (mounted) {
        setState(() => _items =
            (res['items'] as List).map((e) => Map<String, dynamic>.from(e)).toList());
      }
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

  Future<void> _toggle(Map<String, dynamic> item) async {
    final newChecked = !(item['checked'] == true);
    setState(() => item['checked'] = newChecked);
    try {
      await ref.read(userApiProvider).updateShopping(item['id'].toString(),
          checked: newChecked);
    } catch (e) {
      setState(() => item['checked'] = !newChecked);
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    try {
      await ref.read(userApiProvider).deleteShopping(item['id'].toString());
      setState(() => _items.remove(item));
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _add() async {
    final ctrl = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('添加购物项'),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: const InputDecoration(hintText: '比如：鸡蛋、牛奶…'),
          onSubmitted: (v) => Navigator.pop(c, v.trim()),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, ctrl.text.trim()),
              child: const Text('添加')),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    try {
      await ref.read(userApiProvider).addShopping(name);
      _fetch();
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _suggest() async {
    _toast('正在生成补货建议…');
    try {
      final n = await ref.read(userApiProvider).suggestShopping();
      _toast('已添加 $n 项建议');
      _fetch();
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  Future<void> _clearChecked() async {
    try {
      final n = await ref.read(userApiProvider).clearCheckedShopping();
      _toast('已清除 $n 项');
      _fetch();
    } catch (e) {
      _toast(extractError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final checked = _items.where((i) => i['checked'] == true).length;
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('购物清单'),
        actions: [
          IconButton(
            tooltip: 'AI 补货建议',
            icon: const Icon(Icons.auto_awesome),
            onPressed: _suggest,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _add,
        backgroundColor: AppColors.brandPrimary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : Column(
              children: [
                if (_items.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                    child: Row(
                      children: [
                        Text('共 ${_items.length} 项 · 已买 $checked',
                            style: const TextStyle(
                                color: AppColors.textSecondary)),
                        const Spacer(),
                        if (checked > 0)
                          TextButton.icon(
                            onPressed: _clearChecked,
                            icon: const Icon(Icons.cleaning_services, size: 16),
                            label: const Text('清除已买'),
                          ),
                      ],
                    ),
                  ),
                Expanded(
                  child: _items.isEmpty
                      ? _empty()
                      : RefreshIndicator(
                          onRefresh: _fetch,
                          color: AppColors.brandPrimary,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(12, 4, 12, 90),
                            itemCount: _items.length,
                            itemBuilder: (c, i) => _row(_items[i]),
                          ),
                        ),
                ),
              ],
            ),
    );
  }

  Widget _empty() {
    return ListView(children: const [
      SizedBox(height: 120),
      Icon(Icons.shopping_cart_outlined,
          size: 64, color: AppColors.textPlaceholder),
      SizedBox(height: 12),
      Center(
          child: Text('清单是空的，点右下角 + 添加，或右上角让 AI 建议',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary))),
    ]);
  }

  Widget _row(Map<String, dynamic> item) {
    final checked = item['checked'] == true;
    final isAuto = item['source'] == 'auto';
    return Dismissible(
      key: ValueKey(item['id']),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
            color: AppColors.danger, borderRadius: BorderRadius.circular(12)),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => _delete(item),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.borderColor),
        ),
        child: ListTile(
          onTap: () => _toggle(item),
          leading: Icon(
            checked ? Icons.check_circle : Icons.radio_button_unchecked,
            color: checked ? AppColors.success : AppColors.textPlaceholder,
          ),
          title: Text(
            (item['name'] ?? '').toString(),
            style: TextStyle(
              decoration: checked ? TextDecoration.lineThrough : null,
              color: checked ? AppColors.textPlaceholder : AppColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
          subtitle: isAuto
              ? const Text('AI 建议', style: TextStyle(fontSize: 11))
              : null,
          trailing: (item['qty'] ?? 1) > 1
              ? Text('×${item['qty']}',
                  style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w600))
              : null,
        ),
      ),
    );
  }
}
