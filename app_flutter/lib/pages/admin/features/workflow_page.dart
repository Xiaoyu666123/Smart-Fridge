import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/admin_api.dart';

/// 工作流：Agent 工具链 trace 列表 + 步骤时间线 + AI 解释决策。
class WorkflowPage extends ConsumerStatefulWidget {
  const WorkflowPage({super.key});

  @override
  ConsumerState<WorkflowPage> createState() => _WorkflowPageState();
}

class _WorkflowPageState extends ConsumerState<WorkflowPage> {
  bool _loading = true;
  bool _detailLoading = false;
  List<Map<String, dynamic>> _traces = [];
  Map<String, dynamic>? _detail;
  String _filter = '';

  // AI 解释
  String _explanation = '';
  bool _explainLoading = false;
  bool _explainOpen = false;

  static const _agentLabels = {
    'ITEM_IN': '食材入库',
    'ITEM_OUT': '食材取出',
    'CHAT': 'AI 对话',
  };

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() {
      _loading = true;
      _detail = null;
    });
    try {
      final list = await ref
          .read(adminApiProvider)
          .traces(agentType: _filter, limit: 50);
      if (mounted) setState(() => _traces = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _select(String traceId) async {
    setState(() {
      _detailLoading = true;
      _explanation = '';
      _explainOpen = false;
    });
    try {
      final d = await ref.read(adminApiProvider).traceDetail(traceId);
      if (mounted) setState(() => _detail = d);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _detailLoading = false);
    }
  }

  Future<void> _explain() async {
    if (_detail == null) return;
    setState(() => _explainOpen = true);
    if (_explanation.isNotEmpty) return;
    setState(() => _explainLoading = true);
    try {
      final ex = await ref
          .read(adminApiProvider)
          .explainTrace(_detail!['trace_id'].toString());
      if (mounted) setState(() => _explanation = ex.isEmpty ? '暂无解释' : ex);
    } catch (e) {
      if (mounted) {
        setState(() => _explanation = '暂时无法生成解释，请稍后再试。');
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(extractError(e, 'AI 解释失败')),
          backgroundColor: AppColors.danger,
          behavior: SnackBarBehavior.floating,
        ));
      }
    } finally {
      if (mounted) setState(() => _explainLoading = false);
    }
  }

  String _label(String t) => _agentLabels[t] ?? t;

  Color _tagColor(String t) {
    if (t == 'ITEM_IN') return AppColors.success;
    if (t == 'ITEM_OUT') return AppColors.warning;
    return AppColors.brandPrimary;
  }

  String _dur(dynamic ms) {
    if (ms == null) return '-';
    final v = (ms as num).toInt();
    if (v < 1000) return '${v}ms';
    return '${(v / 1000).toStringAsFixed(1)}s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('工作流'),
      ),
      body: _detail != null ? _detailView() : _listView(),
    );
  }

  // ---- 列表视图 ----
  Widget _listView() {
    return Column(
      children: [
        // 筛选
        SizedBox(
          height: 52,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            children: [
              ('', '全部'),
              ('ITEM_IN', '食材入库'),
              ('ITEM_OUT', '食材取出'),
              ('CHAT', 'AI 对话'),
            ].map((f) {
              final sel = _filter == f.$1;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(f.$2),
                  selected: sel,
                  onSelected: (_) {
                    _filter = f.$1;
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
                  child: CircularProgressIndicator(
                      color: AppColors.brandSecondary))
              : _traces.isEmpty
                  ? const Center(child: Text('暂无工具链追踪记录'))
                  : RefreshIndicator(
                      onRefresh: _fetch,
                      color: AppColors.brandSecondary,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: _traces.length,
                        itemBuilder: (c, i) => _traceCard(_traces[i]),
                      ),
                    ),
        ),
      ],
    );
  }

  Widget _traceCard(Map<String, dynamic> t) {
    final type = (t['agent_type'] ?? '').toString();
    final color = _tagColor(type);
    final time = (t['created_at'] ?? '').toString();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: ListTile(
        onTap: () => _select(t['trace_id'].toString()),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(Icons.account_tree, color: color, size: 20),
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(_label(type),
                  style: TextStyle(fontSize: 12, color: color)),
            ),
            const Spacer(),
            Text('${t['step_count']} 步 · ${_dur(t['total_duration_ms'])}',
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textSecondary)),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
              time.length > 19
                  ? time.substring(0, 19).replaceFirst('T', ' ')
                  : time,
              style: const TextStyle(
                  fontSize: 11, color: AppColors.textPlaceholder)),
        ),
        trailing:
            const Icon(Icons.chevron_right, color: AppColors.textPlaceholder),
      ),
    );
  }

  // ---- 详情视图 ----
  Widget _detailView() {
    final steps = (_detail!['steps'] as List?) ?? [];
    final type = (_detail!['agent_type'] ?? '').toString();
    final totalMs = steps.fold<num>(
        0, (s, e) => s + ((e['duration_ms'] ?? 0) as num));

    return Column(
      children: [
        // 顶部返回 + 信息条
        Container(
          padding: const EdgeInsets.all(12),
          color: AppColors.bgCard,
          child: Row(
            children: [
              IconButton(
                onPressed: () => setState(() => _detail = null),
                icon: const Icon(Icons.arrow_back),
              ),
              Expanded(
                child: Text('${_label(type)} 工具链 · ${steps.length} 步 · ${_dur(totalMs)}',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
              ElevatedButton.icon(
                onPressed: _explainLoading ? null : _explain,
                style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.brandPrimary,
                    padding: const EdgeInsets.symmetric(horizontal: 12)),
                icon: _explainLoading
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.auto_awesome, size: 16),
                label: const Text('AI 解释'),
              ),
            ],
          ),
        ),
        Expanded(
          child: _detailLoading
              ? const Center(
                  child: CircularProgressIndicator(
                      color: AppColors.brandSecondary))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_explainOpen) _explainPanel(steps.length),
                    ...steps.asMap().entries.map(
                        (e) => _stepTile(e.key, Map<String, dynamic>.from(e.value),
                            e.key == steps.length - 1)),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _explainPanel(int stepCount) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [
          AppColors.brandPrimary.withValues(alpha: 0.10),
          AppColors.brandPrimary.withValues(alpha: 0.03),
        ]),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.brandPrimaryLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🧠 AI 解释决策',
                  style: TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w700)),
              const Spacer(),
              if (_explanation.isNotEmpty)
                TextButton.icon(
                  onPressed: _explainLoading
                      ? null
                      : () {
                          setState(() => _explanation = '');
                          _explain();
                        },
                  icon: const Icon(Icons.refresh, size: 14),
                  label: const Text('重新生成'),
                ),
            ],
          ),
          const SizedBox(height: 6),
          if (_explainLoading && _explanation.isEmpty)
            Text('正在让 AI 分析这条 $stepCount 步的工具链…',
                style: const TextStyle(
                    fontSize: 13, color: AppColors.textSecondary))
          else
            Text(_explanation,
                style: const TextStyle(fontSize: 14, height: 1.7)),
        ],
      ),
    );
  }

  Widget _stepTile(int i, Map<String, dynamic> step, bool isLast) {
    final tool = (step['tool_name'] ?? '').toString();
    final status = (step['status'] ?? '').toString();
    final ms = step['duration_ms'];
    final ok = status == 'SUCCESS' || status == 'success';
    final input = step['tool_input'];
    final output = step['tool_output'];

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 时间线轴
          Column(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: ok ? AppColors.success : AppColors.danger,
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text('${i + 1}',
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w700)),
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(width: 2, color: AppColors.borderColor),
                ),
            ],
          ),
          const SizedBox(width: 12),
          // 内容
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.borderColor),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(tool,
                            style: const TextStyle(
                                fontSize: 14, fontWeight: FontWeight.w700)),
                      ),
                      Text(_dur(ms),
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.textSecondary)),
                    ],
                  ),
                  if (input != null && input.toString() != '{}' &&
                      input.toString() != 'null') ...[
                    const SizedBox(height: 8),
                    _ioBlock('输入', input),
                  ],
                  if (output != null && output.toString() != '{}' &&
                      output.toString() != 'null') ...[
                    const SizedBox(height: 6),
                    _ioBlock('输出', output),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _ioBlock(String label, dynamic data) {
    String text;
    try {
      text = const JsonEncoder.withIndent('  ').convert(data);
    } catch (_) {
      text = data.toString();
    }
    if (text.length > 300) text = '${text.substring(0, 300)}…';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppColors.textPlaceholder)),
        const SizedBox(height: 2),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppColors.bgSoft,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(text,
              style: const TextStyle(
                  fontSize: 11, fontFamily: 'monospace', height: 1.4)),
        ),
      ],
    );
  }
}
