import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import '../../core/config.dart';
import '../../core/inv_utils.dart';
import '../../api/user_api.dart';

/// 库存查看页（原生镜像 Web 的 Inventory）。
class InventoryTab extends ConsumerStatefulWidget {
  const InventoryTab({super.key});

  @override
  ConsumerState<InventoryTab> createState() => _InventoryTabState();
}

class _InventoryTabState extends ConsumerState<InventoryTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];
  String _keyword = '';

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(userApiProvider).inventory(status: 'IN_STOCK');
      if (mounted) setState(() => _items = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> get _filtered {
    if (_keyword.isEmpty) return _items;
    return _items
        .where((it) => (it['category'] ?? '').toString().contains(_keyword))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('库存查看')),
      body: Column(
        children: [
          // 搜索栏
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              onChanged: (v) => setState(() => _keyword = v.trim()),
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: '搜索食材品类…',
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 12),
              ),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(color: AppColors.brandPrimary))
                : _filtered.isEmpty
                    ? _empty()
                    : RefreshIndicator(
                        onRefresh: _fetch,
                        color: AppColors.brandPrimary,
                        child: GridView.builder(
                          padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                          gridDelegate:
                              const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            childAspectRatio: 0.82,
                            crossAxisSpacing: 10,
                            mainAxisSpacing: 10,
                          ),
                          itemCount: _filtered.length,
                          itemBuilder: (c, i) => _card(_filtered[i]),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _empty() {
    return ListView(
      children: const [
        SizedBox(height: 120),
        Icon(Icons.inbox_outlined, size: 64, color: AppColors.textPlaceholder),
        SizedBox(height: 12),
        Center(
          child: Text('暂无在库食材',
              style: TextStyle(color: AppColors.textSecondary)),
        ),
      ],
    );
  }

  Widget _card(Map<String, dynamic> item) {
    final cat = (item['category'] ?? '未知').toString();
    final brand = item['brand']?.toString();
    final snapshot = item['snapshot_path']?.toString();
    final imgUrl = AppConfig.uploadUrl(snapshot);
    final d = remainDays(item);
    final hasExpiry = d < (1 << 29);

    Color? badgeColor;
    String? badgeText;
    if (hasExpiry) {
      if (d < 0) {
        badgeColor = AppColors.danger;
        badgeText = '已过期';
      } else if (d <= 1) {
        badgeColor = AppColors.warning;
        badgeText = d == 0 ? '今天到期' : '剩1天';
      } else if (d <= 3) {
        badgeColor = const Color(0xFFEAB308);
        badgeText = '剩$d天';
      }
    }

    return Container(
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (imgUrl.isNotEmpty)
                  Image.network(imgUrl, fit: BoxFit.cover,
                      errorBuilder: (c, e, s) => _imgPlaceholder())
                else
                  _imgPlaceholder(),
                if (badgeText != null)
                  Positioned(
                    top: 8,
                    left: 8,
                    child: Container(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                          color: badgeColor,
                          borderRadius: BorderRadius.circular(8)),
                      child: Text(badgeText,
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.w600)),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(cat,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(brand != null && brand.isNotEmpty ? brand : '无品牌信息',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 11, color: AppColors.textPlaceholder)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _imgPlaceholder() {
    return Container(
      color: AppColors.bgSoft,
      child: const Center(
        child: Icon(Icons.restaurant, size: 36, color: AppColors.textPlaceholder),
      ),
    );
  }
}
