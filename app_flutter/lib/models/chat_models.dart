import 'dart:convert';

/// 食谱卡片数据（对齐 Web RecipeCardData）。
class RecipeCard {
  final String name;
  final String? summary;
  final int? prepTime;
  final String? difficulty;
  final List<Map<String, dynamic>> ingredients;
  final List<String> steps;
  final List<String> tags;

  RecipeCard({
    required this.name,
    this.summary,
    this.prepTime,
    this.difficulty,
    this.ingredients = const [],
    this.steps = const [],
    this.tags = const [],
  });

  factory RecipeCard.fromJson(Map<String, dynamic> j) {
    return RecipeCard(
      name: (j['name'] ?? '').toString(),
      summary: j['summary']?.toString(),
      prepTime: j['prep_time'] is num ? (j['prep_time'] as num).toInt() : null,
      difficulty: j['difficulty']?.toString(),
      ingredients: (j['ingredients'] as List?)
              ?.map((e) => Map<String, dynamic>.from(e))
              .toList() ??
          const [],
      steps: (j['steps'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      tags: (j['tags'] as List?)?.map((e) => e.toString()).toList() ?? const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'summary': summary,
        'prep_time': prepTime,
        'difficulty': difficulty,
        'ingredients': ingredients,
        'steps': steps,
        'tags': tags,
      };
}

/// 聊天消息。
class ChatMessage {
  final String role; // user | assistant
  String content; // 展示文本（已剔除 RECIPE 块）
  String parseBuffer; // 流式原始缓冲
  List<RecipeCard> recipes;
  bool structured;
  List<String> invMatched; // 库存问答命中标签
  String kind; // recipe | inventory

  ChatMessage({
    required this.role,
    this.content = '',
    this.parseBuffer = '',
    List<RecipeCard>? recipes,
    this.structured = false,
    List<String>? invMatched,
    this.kind = 'recipe',
  })  : recipes = recipes ?? [],
        invMatched = invMatched ?? [];

  /// 扫描 buffer 抽出完整的 ===RECIPE===...===RECIPE=== 块，解析进 recipes，
  /// 并把已解析的块从展示文本里剔除。
  void parseRecipeBuffer() {
    const marker = '===RECIPE===';
    var buf = parseBuffer;
    while (true) {
      final start = buf.indexOf(marker);
      if (start < 0) break;
      final end = buf.indexOf(marker, start + marker.length);
      if (end < 0) break; // 后半截还没到
      final inner = buf.substring(start + marker.length, end).trim();
      try {
        final obj = jsonDecode(inner) as Map<String, dynamic>;
        if (obj['name'] != null) {
          recipes.add(RecipeCard.fromJson(obj));
        }
      } catch (_) {}
      buf = buf.substring(0, start) + buf.substring(end + marker.length);
    }
    parseBuffer = buf;
    content = buf.trim();
  }
}
