import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import '../../core/dio_client.dart';
import '../../api/admin_api.dart';

/// 设备管理：列表 + 在线状态 + 编辑名称/位置 + 删除。
class DevicesTab extends ConsumerStatefulWidget {
  const DevicesTab({super.key});

  @override
  ConsumerState<DevicesTab> createState() => _DevicesTabState();
}

class _DevicesTabState extends ConsumerState<DevicesTab> {
  bool _loading = true;
  List<Map<String, dynamic>> _devices = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref.read(adminApiProvider).devices();
      if (mounted) setState(() => _devices = list);
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

  ({Color color, String text}) _liveStatus(String s) {
    switch (s) {
      case 'online':
        return (color: AppColors.success, text: '在线');
      case 'idle':
        return (color: AppColors.warning, text: '空闲');
      default:
        return (color: AppColors.textPlaceholder, text: '离线');
    }
  }

  Future<void> _edit(Map<String, dynamic> dev) async {
    final nameCtrl = TextEditingController(text: (dev['name'] ?? '').toString());
    final locCtrl =
        TextEditingController(text: (dev['location'] ?? '').toString());
    final action = await showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text((dev['device_id'] ?? '').toString()),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(labelText: '设备名称')),
            const SizedBox(height: 10),
            TextField(
                controller: locCtrl,
                decoration: const InputDecoration(labelText: '位置')),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, 'delete'),
              child: const Text('删除', style: TextStyle(color: AppColors.danger))),
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, 'save'),
              child: const Text('保存')),
        ],
      ),
    );
    if (action == 'save') {
      try {
        await ref.read(adminApiProvider).updateDevice(
            dev['device_id'].toString(),
            name: nameCtrl.text.trim(),
            location: locCtrl.text.trim());
        _toast('已保存');
        _fetch();
      } catch (e) {
        _toast(extractError(e), error: true);
      }
    } else if (action == 'delete') {
      try {
        await ref.read(adminApiProvider).deleteDevice(dev['device_id'].toString());
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
        title: const Text('设备管理'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : _devices.isEmpty
              ? const Center(child: Text('暂无设备'))
              : RefreshIndicator(
                  onRefresh: _fetch,
                  color: AppColors.brandSecondary,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(14),
                    itemCount: _devices.length,
                    itemBuilder: (c, i) => _card(_devices[i]),
                  ),
                ),
    );
  }

  Widget _card(Map<String, dynamic> dev) {
    final live = _liveStatus((dev['live_status'] ?? 'offline').toString());
    final name = (dev['name'] ?? dev['device_id'] ?? '').toString();
    final loc = (dev['location'] ?? '').toString();
    final hb = dev['heartbeat_count'] ?? 0;
    final lastEvent = (dev['last_event_type'] ?? '').toString();

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
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
                width: 10,
                height: 10,
                decoration:
                    BoxDecoration(color: live.color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(name,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: live.color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(live.text,
                    style: TextStyle(fontSize: 12, color: live.color)),
              ),
              IconButton(
                onPressed: () => _edit(dev),
                icon: const Icon(Icons.more_vert, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text('ID: ${dev['device_id']}',
              style: const TextStyle(
                  fontSize: 12, color: AppColors.textSecondary)),
          if (loc.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Row(children: [
                const Icon(Icons.location_on,
                    size: 14, color: AppColors.textPlaceholder),
                const SizedBox(width: 4),
                Text(loc,
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
              ]),
            ),
          const SizedBox(height: 6),
          Row(
            children: [
              const Icon(Icons.favorite,
                  size: 13, color: AppColors.danger),
              const SizedBox(width: 4),
              Text('心跳 $hb 次',
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textSecondary)),
              if (lastEvent.isNotEmpty) ...[
                const SizedBox(width: 12),
                Text('最近: $lastEvent',
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
