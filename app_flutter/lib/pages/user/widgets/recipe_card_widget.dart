import 'package:flutter/material.dart';
import '../../../core/theme.dart';
import '../../../models/chat_models.dart';

/// 食谱卡片（可展开看食材/步骤，可收藏）。
class RecipeCardWidget extends StatefulWidget {
  final RecipeCard recipe;
  final bool saved;
  final VoidCallback onSave;
  const RecipeCardWidget({
    super.key,
    required this.recipe,
    required this.saved,
    required this.onSave,
  });

  @override
  State<RecipeCardWidget> createState() => _RecipeCardWidgetState();
}

class _RecipeCardWidgetState extends State<RecipeCardWidget> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final r = widget.recipe;
    return Container(
      margin: const EdgeInsets.only(top: 10),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.brandPrimaryLight),
        boxShadow: const [
          BoxShadow(color: Color(0x0F000000), blurRadius: 8, offset: Offset(0, 3)),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 头部
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [
                AppColors.brandPrimary.withValues(alpha: 0.10),
                AppColors.brandPrimary.withValues(alpha: 0.02),
              ]),
            ),
            child: Row(
              children: [
                const Text('🍽️', style: TextStyle(fontSize: 26)),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(r.name,
                          style: const TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w800)),
                      if (r.summary != null && r.summary!.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(r.summary!,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontSize: 12, color: AppColors.textSecondary)),
                      ],
                    ],
                  ),
                ),
                IconButton(
                  onPressed: widget.saved ? null : widget.onSave,
                  icon: Icon(
                    widget.saved ? Icons.favorite : Icons.favorite_border,
                    color: widget.saved
                        ? AppColors.danger
                        : AppColors.textPlaceholder,
                  ),
                ),
              ],
            ),
          ),
          // meta 标签
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
            child: Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                if (r.prepTime != null) _chip('⏱ ${r.prepTime}分钟'),
                if (r.difficulty != null && r.difficulty!.isNotEmpty)
                  _chip('🔥 ${r.difficulty}'),
                ...r.tags.map((t) => _chip(t)),
              ],
            ),
          ),
          // 展开/收起
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(
                children: [
                  Text(_expanded ? '收起' : '查看食材和做法',
                      style: const TextStyle(
                          color: AppColors.brandPrimaryDark,
                          fontWeight: FontWeight.w600,
                          fontSize: 13)),
                  Icon(
                      _expanded
                          ? Icons.keyboard_arrow_up
                          : Icons.keyboard_arrow_down,
                      color: AppColors.brandPrimaryDark,
                      size: 20),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (r.ingredients.isNotEmpty) ...[
                    const Text('🥬 食材',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    ...r.ingredients.map((ing) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Text(
                            '· ${ing['name'] ?? ''}'
                            '${ing['amount'] != null && ing['amount'].toString().isNotEmpty ? '  ${ing['amount']}' : ''}',
                            style: const TextStyle(
                                fontSize: 13, color: AppColors.textSecondary),
                          ),
                        )),
                    const SizedBox(height: 10),
                  ],
                  if (r.steps.isNotEmpty) ...[
                    const Text('👨‍🍳 做法',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    ...r.steps.asMap().entries.map((e) => Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 20,
                                height: 20,
                                alignment: Alignment.center,
                                decoration: const BoxDecoration(
                                  color: AppColors.brandPrimaryLight,
                                  shape: BoxShape.circle,
                                ),
                                child: Text('${e.key + 1}',
                                    style: const TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.brandPrimaryDark)),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(e.value,
                                    style: const TextStyle(
                                        fontSize: 13, height: 1.5)),
                              ),
                            ],
                          ),
                        )),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _chip(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.brandPrimarySoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(text,
          style: const TextStyle(
              fontSize: 11, color: AppColors.brandPrimaryDark)),
    );
  }
}
