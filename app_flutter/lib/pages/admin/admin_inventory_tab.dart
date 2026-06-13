import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import '../../core/config.dart';
import '../../core/inv_utils.dart';
import '../../core/dio_client.dart';
import '../../api/admin_api.dart';

/// 管理端库存管理：分页列表 + 改状态 + 删除。
class AdminInventoryTab extends ConsumerStatefulWidget {
  const AdminInventoryTab({super.key});

  @override
  ConsumerState<AdminInventoryTab> createState() => _AdminInventoryTabState();
}

class _AdminInventoryTabState extends ConsumerState<AdminInventoryTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];
  int _total = 0;
  int _offset = 0;
  final int _limit = 20;
  String _status = '';
  String _q = '';

  static const _statusFilters = [
    ('', '全部'),
    ('IN_STOCK', '在库'),
    ('CONSUMED', '已消耗'),
    ('OUT_PENDING', '待出库'),
  ];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch({bool reset = true}) async {
    if (reset) _offset = 0;
    setState(() => _loading = true);
    try {
      final (items, total) = await ref.read(adminApiProvider).inventoryPaged(
            status: _status,
            q: _q,
            limit: _limit,
            offset: _offset,
          );
      if (mounted) {
        setState(() {
          _items = items;
          _total = total;
        });
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

  Future<void> _edit(Map<String, dynamic> item) async {
    String status = (item['status'] ?? 'IN_STOCK').toString();
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (c) => StatefulBuilder(
        builder: (c, setS) => Padding(
          padding: EdgeInsets.fromLTRB(
              20, 20, 20, 20 + MediaQuery.of(c).viewInsets.bottom),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text((item['category'] ?? '').toString(),
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.w800)),
              const SizedBox(height: 16),
              const Text('修改状态',
                  style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  ('IN_STOCK', '在库'),
                  ('CONSUMED', '已消耗'),
                  ('OUT_PENDING', '待出库'),
                ].map((s) {
                  final sel = status == s.$1;
                  return ChoiceChip(
                    label: Text(s.$2),
                    selected: sel,
                    onSelected: (_) => setS(() => status = s.$1),
                    selectedColor: AppColors.brandPrimaryLight,
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => Navigator.pop(c, 'delete'),
                      style: OutlinedButton.styleFrom(
                          foregroundColor: AppColors.danger,
                          side: const BorderSide(color: AppColors.danger),
                          padding: const EdgeInsets.symmetric(vertical: 12)),
                      icon: const Icon(Icons.delete_outline, size: 18),
                      label: const Text('删除'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      onPressed: () => Navigator.pop(c, 'save:$status'),
                      child: const Text('保存修改'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );

    if (action == null) return;
    if (action == 'delete') {
      try {
        await ref.read(adminApiProvider).deleteInventory(item['id'].toString());
        _toast('已删除');
        _fetch(reset: false);
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    } else if (action.startsWith('save:')) {
      final newStatus = action.substring(5);
      try {
        await ref.read(adminApiProvider).updateInventory(
            item['id'].toString(), {'status': newStatus});
        _toast('已更新');
        _fetch(reset: false);
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final totalPages = (_total / _limit).ceil();
    final curPage = (_offset / _limit).floor() + 1;
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('库存管理'),
      ),
      body: Column(
        children: [
          // 搜索 + 筛选
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
            child: TextField(
              onSubmitted: (v) {
                _q = v.trim();
                _fetch();
              },
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: '搜索品类，回车搜索',
                isDense: true,
              ),
            ),
          ),
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: _statusFilters.map((s) {
                final sel = _status == s.$1;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(s.$2),
                    selected: sel,
                    onSelected: (_) {
                      _status = s.$1;
                      _fetch();
                    },
                    selectedColor: AppColors.brandSecondaryLight,
                  ),
                );
              }).toList(),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child:
                        CircularProgressIndicator(color: AppColors.brandSecondary))
                : _items.isEmpty
                    ? const Center(child: Text('没有匹配的库存'))
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: _items.length,
                        itemBuilder: (c, i) => _row(_items[i]),
                      ),
          ),
          // 分页
          if (totalPages > 1)
            Container(
              padding: EdgeInsets.fromLTRB(
                  16, 8, 16, 8 + MediaQuery.of(context).padding.bottom),
              color: AppColors.bgCard,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    onPressed: _offset > 0
                        ? () {
                            _offset -= _limit;
                            _fetch(reset: false);
                          }
                        : null,
                    icon: const Icon(Icons.chevron_left),
                  ),
                  Text('$curPage / $totalPages  (共 $_total)'),
                  IconButton(
                    onPressed: curPage < totalPages
                        ? () {
                            _offset += _limit;
                            _fetch(reset: false);
                          }
                        : null,
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _row(Map<String, dynamic> item) {
    final cat = (item['category'] ?? '未知').toString();
    final status = (item['status'] ?? '').toString();
    final img = AppConfig.uploadUrl(item['snapshot_path']?.toString());
    final d = remainDays(item);

    Color statusColor = AppColors.textSecondary;
    String statusText = status;
    if (status == 'IN_STOCK') {
      statusColor = AppColors.success;
      statusText = '在库';
    } else if (status == 'CONSUMED') {
      statusColor = AppColors.textPlaceholder;
      statusText = '已消耗';
    } else if (status == 'OUT_PENDING') {
      statusColor = AppColors.warning;
      statusText = '待出库';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: ListTile(
        onTap: () => _edit(item),
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: img.isNotEmpty
              ? Image.network(img,
                  width: 48,
                  height: 48,
                  fit: BoxFit.cover,
                  errorBuilder: (c, e, s) => _imgPh())
              : _imgPh(),
        ),
        title: Text(cat, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(statusText,
                  style: TextStyle(fontSize: 11, color: statusColor)),
            ),
            if (status == 'IN_STOCK' && hasExpiry(item)) ...[
              const SizedBox(width: 6),
              Text(d < 0 ? '已过期' : '剩 $d 天',
                  style: TextStyle(
                      fontSize: 11,
                      color: d <= 3 ? AppColors.warning : AppColors.textSecondary)),
            ],
          ],
        ),
        trailing: const Icon(Icons.edit, size: 18, color: AppColors.textPlaceholder),
      ),
    );
  }

  Widget _imgPh() => Container(
        width: 48,
        height: 48,
        color: AppColors.bgSoft,
        child: const Icon(Icons.restaurant, size: 22, color: AppColors.textPlaceholder),
      );
}
