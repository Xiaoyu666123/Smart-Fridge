import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/admin_api.dart';

/// 品类配置：临期阈值天数 + 单价。
class CategoryConfigPage extends ConsumerStatefulWidget {
  const CategoryConfigPage({super.key});

  @override
  ConsumerState<CategoryConfigPage> createState() =>
      _CategoryConfigPageState();
}

class _CategoryConfigPageState extends ConsumerState<CategoryConfigPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _rows = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(adminApiProvider).thresholds();
      if (mounted) setState(() => _rows = list);
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

  Future<void> _edit(Map<String, dynamic> row) async {
    final daysCtrl = TextEditingController(
        text: (row['days_before_expiry'] ?? '').toString());
    final priceCtrl = TextEditingController(
        text: row['unit_price'] != null ? row['unit_price'].toString() : '');
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text('配置「${row['category']}」'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: daysCtrl,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: '临期提前天数', suffixText: '天'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: priceCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration:
                  const InputDecoration(labelText: '单价(用于浪费金额估算)', prefixText: '¥'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('保存')),
        ],
      ),
    );
    if (ok == true) {
      try {
        await ref.read(adminApiProvider).updateThreshold(
              row['id'].toString(),
              daysBeforeExpiry: int.tryParse(daysCtrl.text.trim()),
              unitPrice: double.tryParse(priceCtrl.text.trim()),
            );
        _toast('已保存');
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
        title: const Text('品类配置'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : RefreshIndicator(
              onRefresh: _fetch,
              color: AppColors.brandSecondary,
              child: ListView.builder(
                padding: const EdgeInsets.all(14),
                itemCount: _rows.length,
                itemBuilder: (c, i) {
                  final r = _rows[i];
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    decoration: BoxDecoration(
                      color: AppColors.bgCard,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.borderColor),
                    ),
                    child: ListTile(
                      onTap: () => _edit(r),
                      title: Text((r['category'] ?? '').toString(),
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text(
                          '临期提前 ${r['days_before_expiry']} 天'
                          '${r['unit_price'] != null ? ' · 单价 ¥${r['unit_price']}' : ' · 未设单价'}',
                          style: const TextStyle(fontSize: 12)),
                      trailing: const Icon(Icons.edit,
                          size: 18, color: AppColors.textPlaceholder),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
