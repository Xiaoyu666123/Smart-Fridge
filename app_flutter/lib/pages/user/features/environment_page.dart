import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme.dart';
import '../../../api/user_api.dart';

/// 环境信息：天气 + 季节。
class EnvironmentPage extends ConsumerStatefulWidget {
  const EnvironmentPage({super.key});

  @override
  ConsumerState<EnvironmentPage> createState() => _EnvironmentPageState();
}

class _EnvironmentPageState extends ConsumerState<EnvironmentPage> {
  bool _loading = true;
  Map<String, dynamic>? _env;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final env = await ref.read(userApiProvider).environment();
      if (mounted) setState(() => _env = env);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _weatherEmoji(String desc) {
    if (desc.contains('雨')) return '🌧';
    if (desc.contains('云')) return '⛅';
    if (desc.contains('阴')) return '☁️';
    if (desc.contains('雪')) return '❄️';
    if (desc.contains('雷')) return '⛈';
    return '☀️';
  }

  @override
  Widget build(BuildContext context) {
    final e = _env;
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      appBar: AppBar(title: const Text('环境信息')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.brandPrimary))
          : e == null
              ? const Center(child: Text('天气信息获取失败'))
              : RefreshIndicator(
                  onRefresh: _fetch,
                  color: AppColors.brandPrimary,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      // 大天气卡
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [
                              AppColors.brandPrimaryHover,
                              AppColors.brandPrimaryDark
                            ],
                          ),
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: [
                            BoxShadow(
                                color: AppColors.brandPrimary
                                    .withValues(alpha: 0.3),
                                blurRadius: 20,
                                offset: const Offset(0, 8)),
                          ],
                        ),
                        child: Column(
                          children: [
                            Text(
                                _weatherEmoji(
                                    (e['weather_desc'] ?? '').toString()),
                                style: const TextStyle(fontSize: 64)),
                            const SizedBox(height: 8),
                            Text('${e['temperature'] ?? '--'}°',
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 48,
                                    fontWeight: FontWeight.w800)),
                            Text(
                                '${e['weather_desc'] ?? ''} · ${e['city'] ?? ''}',
                                style: const TextStyle(
                                    color: Colors.white, fontSize: 16)),
                            if (e['feels_like'] != null)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text('体感 ${e['feels_like']}°',
                                    style: TextStyle(
                                        color: Colors.white
                                            .withValues(alpha: 0.85),
                                        fontSize: 13)),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                      // 指标网格
                      GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        childAspectRatio: 2.2,
                        mainAxisSpacing: 10,
                        crossAxisSpacing: 10,
                        children: [
                          _metric('💧 湿度', e['humidity'], '%'),
                          _metric('🌬 风速', e['wind_speed'], ' km/h'),
                          _metric('🧭 风向', e['wind_dir'], ''),
                          _metric('☀️ 紫外线', e['uv_index'], ''),
                          _metric('👁 能见度', e['visibility'], ' km'),
                          _metric('🌡 气压', e['pressure'], ' hPa'),
                          _metric('☁️ 云量', e['cloudcover'], '%'),
                          _metric('🍃 季节', e['season'], ''),
                        ],
                      ),
                      const SizedBox(height: 16),
                      if (e['sunrise'] != null || e['sunset'] != null)
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: AppColors.bgCard,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: AppColors.borderColor),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceAround,
                            children: [
                              _sun('🌅 日出', e['sunrise']),
                              Container(
                                  width: 1,
                                  height: 36,
                                  color: AppColors.borderColor),
                              _sun('🌇 日落', e['sunset']),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
    );
  }

  Widget _metric(String label, dynamic value, String unit) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label,
              style: const TextStyle(
                  fontSize: 12, color: AppColors.textSecondary)),
          const SizedBox(height: 4),
          Text('${value ?? '--'}$unit',
              style: const TextStyle(
                  fontSize: 18, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }

  Widget _sun(String label, dynamic time) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 13)),
        const SizedBox(height: 4),
        Text((time ?? '--').toString(),
            style: const TextStyle(
                fontSize: 16, fontWeight: FontWeight.w700)),
      ],
    );
  }
}
