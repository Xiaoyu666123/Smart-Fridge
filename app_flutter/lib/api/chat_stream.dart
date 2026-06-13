import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import '../core/config.dart';

/// AI 食谱流式对话（SSE）。
///
/// 后端：GET /api/v1/user/agent/chat/stream?message=&city=&structured=true
/// Token 通过 Authorization Header 传递，避免出现在 URL 日志中。
/// 事件流：每行 `data: {json}`，json.type ∈ delta|done|error。
class ChatStream {
  /// 发起一次流式请求，返回一个可监听的事件流。
  /// 调用方负责 listen 并在结束/离开时 cancel。
  static Stream<ChatEvent> stream({
    required String message,
    required String token,
    String? city,
    bool structured = true,
  }) async* {
    final dio = Dio();
    final params = <String, String>{
      'message': message,
      if (city != null && city.isNotEmpty) 'city': city,
      if (structured) 'structured': 'true',
    };
    final url = '${AppConfig.userBase}/agent/chat/stream';

    final resp = await dio.get<ResponseBody>(
      url,
      queryParameters: params,
      options: Options(
        responseType: ResponseType.stream,
        receiveTimeout: const Duration(minutes: 3),
        headers: {
          'Accept': 'text/event-stream',
          if (token.isNotEmpty) 'Authorization': 'Bearer $token',
        },
      ),
    );

    final stream = resp.data!.stream;
    final decoder = const Utf8Decoder();
    String buffer = '';

    await for (final chunk in stream) {
      buffer += decoder.convert(chunk);
      // 按行处理；SSE 以 \n 分隔，data: 开头
      int idx;
      while ((idx = buffer.indexOf('\n')) >= 0) {
        final line = buffer.substring(0, idx).trim();
        buffer = buffer.substring(idx + 1);
        if (line.isEmpty) continue;
        if (!line.startsWith('data:')) continue;
        final jsonStr = line.substring(5).trim();
        if (jsonStr.isEmpty) continue;
        try {
          final data = jsonDecode(jsonStr) as Map<String, dynamic>;
          final type = data['type'];
          if (type == 'delta') {
            yield ChatEvent.delta(data['content']?.toString() ?? '');
          } else if (type == 'done') {
            final prefs = (data['detected_preferences'] as List?)
                    ?.map((e) => Map<String, dynamic>.from(e))
                    .toList() ??
                [];
            yield ChatEvent.done(prefs);
            return;
          } else if (type == 'error') {
            yield ChatEvent.error(data['message']?.toString() ?? '请求失败');
            return;
          }
        } catch (_) {
          // 忽略无法解析的行
        }
      }
    }
  }
}

enum ChatEventType { delta, done, error }

class ChatEvent {
  final ChatEventType type;
  final String content;
  final List<Map<String, dynamic>> preferences;

  ChatEvent.delta(this.content)
      : type = ChatEventType.delta,
        preferences = const [];
  ChatEvent.done(this.preferences)
      : type = ChatEventType.done,
        content = '';
  ChatEvent.error(this.content)
      : type = ChatEventType.error,
        preferences = const [];
}
