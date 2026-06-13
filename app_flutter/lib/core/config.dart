/// 全局配置中心。
///
/// [apiBase] 支持三种方式覆盖（优先级从高到低）：
///   1. 编译时 --dart-define=API_BASE=https://your-server.com
///   2. 直接改下面的默认值
///   3. 保留当前默认局域网地址（仅限开发）
class AppConfig {
  /// 后端根地址（不含 /api/v1，结尾不要斜杠）。
  /// 生产环境请改为 https 域名。
  static const String apiBase = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'http://192.168.31.19:8000',
  );

  /// REST 前缀
  static String get apiPrefix => '$apiBase/api/v1';

  /// 用户端接口前缀：/api/v1/user
  static String get userBase => '$apiPrefix/user';

  /// 管理端接口前缀：/api/v1/admin
  static String get adminBase => '$apiPrefix/admin';

  /// 拼接上传图片地址。后端返回的可能是文件名或路径。
  static String uploadUrl(String? pathOrName) {
    if (pathOrName == null || pathOrName.isEmpty) return '';
    if (pathOrName.startsWith('http://') || pathOrName.startsWith('https://')) {
      return pathOrName;
    }
    final filename = pathOrName.replaceAll('\\', '/').split('/').last;
    return '$apiBase/uploads/$filename';
  }

  /// WebSocket 地址（http->ws, https->wss）。
  static String wsUrl(String path) {
    final p = path.startsWith('/') ? path : '/$path';
    final wsBase = apiBase.replaceFirst(RegExp(r'^http'), 'ws');
    return '$wsBase/api/v1$p';
  }
}
