import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/dio_client.dart';

/// 管理端接口封装。基于 adminDio（baseURL=/api/v1/admin）。
class AdminApi {
  final Dio _dio;
  AdminApi(this._dio);

  // ---- 库存 ----
  /// 分页拉库存，返回 (items, total)。total 来自响应头 X-Total-Count。
  Future<(List<Map<String, dynamic>>, int)> inventoryPaged({
    String? status,
    String? category,
    String? q,
    int limit = 20,
    int offset = 0,
  }) async {
    final res = await _dio.get('/inventory', queryParameters: {
      if (status != null && status.isNotEmpty) 'status': status,
      if (category != null && category.isNotEmpty) 'category': category,
      if (q != null && q.isNotEmpty) 'q': q,
      'limit': limit,
      'offset': offset,
    });
    final items =
        (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
    final totalHeader = res.headers.value('X-Total-Count');
    final total = totalHeader != null ? int.tryParse(totalHeader) ?? items.length : items.length;
    return (items, total);
  }

  Future<List<Map<String, dynamic>>> inventory({String? status}) async {
    final res = await _dio.get('/inventory',
        queryParameters: {if (status != null) 'status': status});
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<List<String>> categories() async {
    final res = await _dio.get('/inventory/categories');
    return (res.data as List).map((e) => e.toString()).toList();
  }

  Future<void> updateInventory(String id, Map<String, dynamic> data) async {
    await _dio.put('/inventory/$id', data: data);
  }

  Future<void> deleteInventory(String id) async {
    await _dio.delete('/inventory/$id');
  }

  // ---- 事件 ----
  Future<List<Map<String, dynamic>>> events() async {
    final res = await _dio.get('/events');
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  // ---- 设备 ----
  Future<List<Map<String, dynamic>>> devices() async {
    final res = await _dio.get('/devices');
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<void> updateDevice(String deviceId,
      {String? name, String? location, String? description}) async {
    await _dio.put('/devices/$deviceId', data: {
      if (name != null) 'name': name,
      if (location != null) 'location': location,
      if (description != null) 'description': description,
    });
  }

  Future<void> deleteDevice(String deviceId) async {
    await _dio.delete('/devices/$deviceId');
  }

  // ---- 用户管理 ----
  Future<List<Map<String, dynamic>>> users({String? search}) async {
    final res = await _dio.get('/users',
        queryParameters: {if (search != null && search.isNotEmpty) 'search': search});
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<Map<String, dynamic>> createUser(String username, String password) async {
    final res = await _dio.post('/users',
        data: {'username': username, 'password': password});
    return Map<String, dynamic>.from(res.data);
  }

  Future<void> resetUserPassword(String userId, String newPassword) async {
    await _dio.put('/users/$userId/password', data: {'new_password': newPassword});
  }

  Future<void> deleteUser(String userId) async {
    await _dio.delete('/users/$userId');
  }

  // ---- 品类配置 ----
  Future<List<Map<String, dynamic>>> thresholds() async {
    final res = await _dio.get('/category-thresholds');
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<void> updateThreshold(String id,
      {int? daysBeforeExpiry, double? unitPrice}) async {
    await _dio.put('/category-thresholds/$id', data: {
      if (daysBeforeExpiry != null) 'days_before_expiry': daysBeforeExpiry,
      if (unitPrice != null) 'unit_price': unitPrice,
    });
  }

  // ---- 操作审计 / 日志 ----
  Future<List<Map<String, dynamic>>> logs({
    String? source,
    String? eventType,
    String? status,
    int limit = 50,
    int offset = 0,
  }) async {
    final res = await _dio.get('/logs', queryParameters: {
      if (source != null) 'source': source,
      if (eventType != null) 'event_type': eventType,
      if (status != null) 'status': status,
      'limit': limit,
      'offset': offset,
    });
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  // ---- Token 用量 ----
  Future<Map<String, dynamic>> usageSummary({int days = 30}) async {
    final res = await _dio.get('/usage/summary', queryParameters: {'days': days});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 浪费分析 ----
  Future<Map<String, dynamic>> wasteAnalytics({int days = 30}) async {
    final res = await _dio.get('/stats/waste', queryParameters: {'days': days});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 性能监控 ----
  Future<Map<String, dynamic>> perfStats({int hours = 24}) async {
    final res = await _dio.get('/stats/perf', queryParameters: {'hours': hours});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 营养（大盘可复用）----
  Future<Map<String, dynamic>> nutrition({int days = 30}) async {
    final res = await _dio.get('/stats/nutrition', queryParameters: {'days': days});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- Agent 配置 ----
  Future<Map<String, dynamic>> agentConfig() async {
    final res = await _dio.get('/agent/config');
    return Map<String, dynamic>.from(res.data);
  }

  Future<Map<String, dynamic>> visionAssistConfig() async {
    final res = await _dio.get('/agent/vision-assist-config');
    return Map<String, dynamic>.from(res.data);
  }

  Future<void> updateVisionAssistConfig(double lower, double upper) async {
    await _dio.put('/agent/vision-assist-config',
        data: {'lower': lower, 'upper': upper});
  }

  // ---- 标签缓冲 ----
  Future<List<Map<String, dynamic>>> pendingLabels({String? status}) async {
    final res = await _dio.get('/pending-labels',
        queryParameters: {if (status != null) 'status': status});
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<void> deletePendingLabel(String id) async {
    await _dio.delete('/pending-labels/$id');
  }

  // ---- Trace 列表 ----
  Future<List<Map<String, dynamic>>> traces({String? agentType, int limit = 50}) async {
    final res = await _dio.get('/traces', queryParameters: {
      if (agentType != null && agentType.isNotEmpty) 'agent_type': agentType,
      'limit': limit,
    });
    return (res.data as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Future<Map<String, dynamic>> traceDetail(String traceId) async {
    final res = await _dio.get('/traces/$traceId');
    return Map<String, dynamic>.from(res.data);
  }

  Future<String> explainTrace(String traceId) async {
    final res = await _dio.get('/traces/$traceId/explain',
        options: Options(receiveTimeout: const Duration(seconds: 90)));
    return (res.data['explanation'] ?? '').toString();
  }

  // ---- 整柜批量识别 / 入库 ----
  Future<List<Map<String, dynamic>>> detect(String base64Image) async {
    final res = await _dio.post('/agent/detect',
        data: {'image': base64Image},
        options: Options(receiveTimeout: const Duration(seconds: 90)));
    return (res.data['items'] as List)
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  Future<Map<String, dynamic>> bulkCreate(
      String deviceId, List<Map<String, dynamic>> items) async {
    final res = await _dio.post('/inventory/bulk',
        data: {'device_id': deviceId, 'items': items});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 食材生命周期 Sankey ----
  Future<Map<String, dynamic>> lifecycle({int days = 30, int topN = 8}) async {
    final res = await _dio.get('/stats/lifecycle',
        queryParameters: {'days': days, 'top_n': topN});
    return Map<String, dynamic>.from(res.data);
  }

  // ---- 浪费日历热图 ----
  Future<Map<String, dynamic>> wasteCalendar({int days = 365}) async {
    final res =
        await _dio.get('/stats/waste-calendar', queryParameters: {'days': days});
    return Map<String, dynamic>.from(res.data);
  }
}

final adminApiProvider = Provider<AdminApi>((ref) {
  return AdminApi(ref.watch(adminDioProvider));
});
