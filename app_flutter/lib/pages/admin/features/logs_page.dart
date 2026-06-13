import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/admin_api.dart';

/// 系统日志 / 操作审计（同一 /logs 接口）。
class LogsPage extends ConsumerStatefulWidget {
  final String title;
  final String? source; // 'admin' = 操作审计；null = 全部
  const LogsPage({super.key, required this.title, this.source});

  @override
  ConsumerState<LogsPage> createState() => _LogsPageState();
}

class _LogsPageState extends ConsumerState<LogsPage> {
  bool _loading = true;
  List<Map<String, dynamic>> _logs = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final list = await ref
          .read(adminApiProvider)
          .logs(source: widget.source, limit: 100);
      if (mounted) setState(() => _logs = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _statusColor(String s) {
    if (s == 'SUCCESS') return AppColors.success;
    if (s == 'FAILED' || s == 'ERROR') return AppColors.danger;
    return AppColors.textSecondary;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: Text(widget.title),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : _logs.isEmpty
              ? const Center(child: Text('暂无日志'))
              : RefreshIndicator(
                  onRefresh: _fetch,
                  color: AppColors.brandSecondary,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(14),
                    itemCount: _logs.length,
                    itemBuilder: (c, i) => _row(_logs[i]),
                  ),
                ),
    );
  }

  Widget _row(Map<String, dynamic> log) {
    final type = (log['event_type'] ?? '').toString();
    final src = (log['source'] ?? '').toString();
    final status = (log['status'] ?? '').toString();
    final time = (log['created_at'] ?? '').toString();
    final detail = log['detail'];
    String detailStr = '';
    if (detail is Map && detail.isNotEmpty) {
      detailStr = const JsonEncoder.withIndent('  ').convert(detail);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
          title: Row(
            children: [
              Expanded(
                child: Text(type,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: _statusColor(status).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(status,
                    style: TextStyle(
                        fontSize: 11, color: _statusColor(status))),
              ),
            ],
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('$src · ${time.length > 19 ? time.substring(0, 19).replaceFirst('T', ' ') : time}',
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textPlaceholder)),
          ),
          children: detailStr.isEmpty
              ? [const Text('无详情', style: TextStyle(color: AppColors.textPlaceholder))]
              : [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.bgSoft,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(detailStr,
                        style: const TextStyle(
                            fontSize: 12,
                            fontFamily: 'monospace',
                            height: 1.5)),
                  ),
                ],
        ),
      ),
    );
  }
}
