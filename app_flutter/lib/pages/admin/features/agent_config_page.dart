import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../core/dio_client.dart';
import '../../../api/admin_api.dart';

/// Agent 配置：视觉/LLM 模型状态 + 视觉辅助识别区间策略。
class AgentConfigPage extends ConsumerStatefulWidget {
  const AgentConfigPage({super.key});

  @override
  ConsumerState<AgentConfigPage> createState() => _AgentConfigPageState();
}

class _AgentConfigPageState extends ConsumerState<AgentConfigPage> {
  bool _loading = true;
  Map<String, dynamic>? _config;
  Map<String, dynamic>? _vision;
  RangeValues _range = const RangeValues(0.3, 0.7);
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    final api = ref.read(adminApiProvider);
    final r = await Future.wait([
      api.agentConfig().then<Map<String, dynamic>?>((v) => v).catchError((_) => null),
      api.visionAssistConfig().then<Map<String, dynamic>?>((v) => v).catchError((_) => null),
    ]);
    if (!mounted) return;
    setState(() {
      _config = r[0];
      _vision = r[1];
      if (_vision != null) {
        _range = RangeValues(
          ((_vision!['lower'] ?? 0.3) as num).toDouble(),
          ((_vision!['upper'] ?? 0.7) as num).toDouble(),
        );
      }
      _loading = false;
    });
  }

  Future<void> _saveRange() async {
    setState(() => _saving = true);
    try {
      await ref.read(adminApiProvider)
          .updateVisionAssistConfig(_range.start, _range.end);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('已保存视觉辅助区间'),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(extractError(e)),
          backgroundColor: AppColors.danger,
          behavior: SnackBarBehavior.floating,
        ));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = _config;
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(
        title: const Text('Agent 配置'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandSecondary))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text('模型状态',
                    style:
                        TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                const SizedBox(height: 10),
                _modelCard('👁 视觉模型', c?['vision_model'], c?['vision_status']),
                const SizedBox(height: 8),
                _modelCard('🧠 语言模型', c?['llm_model'], c?['llm_status']),
                const SizedBox(height: 24),
                const Text('视觉辅助识别区间',
                    style:
                        TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                const Text('端侧置信度落在区间内时，触发云端 VLM 复核',
                    style: TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.bgCard,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.borderColor),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('下限 ${_range.start.toStringAsFixed(2)}',
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600)),
                          Text('上限 ${_range.end.toStringAsFixed(2)}',
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600)),
                        ],
                      ),
                      RangeSlider(
                        values: _range,
                        min: 0,
                        max: 1,
                        divisions: 100,
                        activeColor: AppColors.brandSecondary,
                        labels: RangeLabels(
                          _range.start.toStringAsFixed(2),
                          _range.end.toStringAsFixed(2),
                        ),
                        onChanged: (v) {
                          if (v.start < v.end) setState(() => _range = v);
                        },
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '< ${_range.start.toStringAsFixed(2)} 直接采纳端侧 · '
                        '${_range.start.toStringAsFixed(2)}~${_range.end.toStringAsFixed(2)} 云端复核 · '
                        '> ${_range.end.toStringAsFixed(2)} 高置信直接采纳',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                            fontSize: 11, color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: _saving ? null : _saveRange,
                          style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.brandSecondary),
                          child: _saving
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2, color: Colors.white))
                              : const Text('保存区间'),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _modelCard(String label, dynamic model, dynamic status) {
    final ok = status == '已连接';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text((model ?? '--').toString(),
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: (ok ? AppColors.success : AppColors.textPlaceholder)
                  .withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text((status ?? '未知').toString(),
                style: TextStyle(
                    fontSize: 12,
                    color: ok ? AppColors.success : AppColors.textPlaceholder)),
          ),
        ],
      ),
    );
  }
}
