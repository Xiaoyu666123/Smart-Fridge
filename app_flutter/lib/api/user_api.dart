import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/dio_client.dart';

/// 用户端接口封装。基于 userDio（baseURL=/api/v1/user）。
class UserApi {
  final Dio _dio;
  UserApi(this._dio);

  /// 库存列表 GET /inventory
  Future<List<Map<String, dynamic>>> inventory({
    String? status,
    String? category,
    String? q,
    int? expiringInDays,
  }) async {
    final res = await _dio.get('/inventory', queryParameters: {
      if (status != null) 'status': status,
      if (category != null) 'category': category,
      if (q != null) 'q': q,
      if (expiringInDays != null) 'expiring_in_days': expiringInDays,
    });
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  /// 品类列表 GET /inventory/categories
  Future<List<String>> categories() async {
    final res = await _dio.get('/inventory/categories');
    return (res.data as List).map((e) => e.toString()).toList();
  }

  /// 环境天气 GET /environment
  Future<Map<String, dynamic>> environment([String? city]) async {
    final res = await _dio.get('/environment',
        queryParameters: city != null ? {'city': city} : null);
    return Map<String, dynamic>.from(res.data);
  }

  /// 营养报告 GET /stats/nutrition
  Future<Map<String, dynamic>> nutrition({int days = 7}) async {
    final res = await _dio.get('/stats/nutrition', queryParameters: {'days': days});
    return Map<String, dynamic>.from(res.data);
  }

  /// 未读通知数 GET /notifications/count
  Future<int> unreadCount() async {
    final res = await _dio.get('/notifications/count');
    return (res.data['unread_count'] ?? 0) as int;
  }

  /// 通知列表 GET /notifications
  Future<List<Map<String, dynamic>>> notifications() async {
    final res = await _dio.get('/notifications');
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  /// 收藏的食谱 GET /recipes
  Future<List<Map<String, dynamic>>> savedRecipes({int limit = 50}) async {
    final res = await _dio.get('/recipes', queryParameters: {'limit': limit});
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  /// 每日小贴士 GET /agent/daily-tip
  Future<Map<String, dynamic>> dailyTip({bool refresh = false}) async {
    final res = await _dio.get('/agent/daily-tip',
        queryParameters: refresh ? {'refresh': true} : null,
        options: Options(receiveTimeout: const Duration(seconds: 90)));
    return Map<String, dynamic>.from(res.data);
  }

  /// 自然语言库存查询 POST /agent/inventory-query
  Future<Map<String, dynamic>> inventoryQuery(String question) async {
    final res = await _dio.post('/agent/inventory-query',
        data: {'question': question},
        options: Options(receiveTimeout: const Duration(seconds: 60)));
    return Map<String, dynamic>.from(res.data);
  }

  /// 食材识别 POST /agent/recognize  body {image: base64}
  /// 返回 {category, confidence, shelf_life_days, storage_advice}
  Future<Map<String, dynamic>> recognize(String base64Image) async {
    final res = await _dio.post('/agent/recognize',
        data: {'image': base64Image},
        options: Options(receiveTimeout: const Duration(seconds: 90)));
    return Map<String, dynamic>.from(res.data);
  }

  /// 历史对话 GET /agent/conversations
  /// 返回扁平消息流 [{id, role, content, created_at}]
  Future<List<Map<String, dynamic>>> conversations({int limit = 100}) async {
    final res = await _dio.get('/agent/conversations',
        queryParameters: {'limit': limit});
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  /// 收藏食谱 POST /recipes
  Future<Map<String, dynamic>> saveRecipe(Map<String, dynamic> recipe) async {
    final res = await _dio.post('/recipes', data: recipe);
    return Map<String, dynamic>.from(res.data);
  }

  /// 删除收藏食谱 DELETE /recipes/{id}
  Future<void> deleteRecipe(String id) async {
    await _dio.delete('/recipes/$id');
  }

  /// 更新食谱评分/笔记 PUT /recipes/{id}
  Future<Map<String, dynamic>> updateRecipeMeta(String id,
      {int? rating, String? notes}) async {
    final res = await _dio.put('/recipes/$id', data: {
      if (rating != null) 'rating': rating,
      if (notes != null) 'notes': notes,
    });
    return Map<String, dynamic>.from(res.data);
  }

  /// 做这道菜（打卡）POST /recipes/{id}/cook
  Future<Map<String, dynamic>> cookRecipe(String id,
      {List<String> consumedIds = const []}) async {
    final res = await _dio.post('/recipes/$id/cook',
        data: {'consumed_inventory_ids': consumedIds});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 购物清单 ----
  Future<Map<String, dynamic>> shoppingList() async {
    final res = await _dio.get('/shopping');
    return Map<String, dynamic>.from(res.data);
  }

  Future<Map<String, dynamic>> addShopping(String name, {int qty = 1}) async {
    final res = await _dio.post('/shopping', data: {'name': name, 'qty': qty});
    return Map<String, dynamic>.from(res.data);
  }

  Future<void> updateShopping(String id, {bool? checked, int? qty}) async {
    await _dio.put('/shopping/$id', data: {
      if (checked != null) 'checked': checked,
      if (qty != null) 'qty': qty,
    });
  }

  Future<void> deleteShopping(String id) async {
    await _dio.delete('/shopping/$id');
  }

  Future<int> clearCheckedShopping() async {
    final res = await _dio.post('/shopping/clear-checked');
    return (res.data['removed'] ?? 0) as int;
  }

  Future<int> suggestShopping() async {
    final res = await _dio.post('/shopping/suggest');
    return (res.data['added_count'] ?? 0) as int;
  }

  // ---- 营养 / 成就 ----
  Future<Map<String, dynamic>> achievements() async {
    final res = await _dio.get('/stats/achievements');
    return Map<String, dynamic>.from(res.data);
  }

  /// AI 营养教练 GET /agent/coach
  Future<Map<String, dynamic>> coach({int days = 30}) async {
    final res = await _dio.get('/agent/coach',
        queryParameters: {'days': days},
        options: Options(receiveTimeout: const Duration(seconds: 90)));
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 偏好设置 ----
  Future<List<Map<String, dynamic>>> preferences() async {
    final res = await _dio.get('/agent/preferences');
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<Map<String, dynamic>> addPreference(String key, String value) async {
    final res = await _dio.post('/agent/preferences',
        data: {'preference_key': key, 'preference_value': value});
    return Map<String, dynamic>.from(res.data);
  }

  Future<void> deletePreference(String id) async {
    await _dio.delete('/agent/preferences/$id');
  }
}

final userApiProvider = Provider<UserApi>((ref) {
  return UserApi(ref.watch(userDioProvider));
});
