import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 登录身份类型
enum Role { none, user, admin }

/// 登录状态保持时长：1 天。超过则要求重新登录。
const Duration kLoginValidity = Duration(days: 1);

/// 安全存储实例（Token 等敏感信息）
const _secure = FlutterSecureStorage(
  aOptions: AndroidOptions(encryptedSharedPreferences: true),
);

/// 非敏感配置 key
const _prefsKeyAuthMeta = 'auth_meta';

/// 鉴权状态：双 token（user / admin），token 存安全存储，元数据存 SharedPreferences。
@immutable
class AuthState {
  final String userToken;
  final String userId;
  final String username;
  final String adminToken;
  final String adminId;
  final String adminName;

  /// 登录时间（epoch 毫秒）。用于判断是否超过 [kLoginValidity]。
  final int userLoginAt;
  final int adminLoginAt;

  const AuthState({
    this.userToken = '',
    this.userId = '',
    this.username = '',
    this.adminToken = '',
    this.adminId = '',
    this.adminName = '',
    this.userLoginAt = 0,
    this.adminLoginAt = 0,
  });

  bool get isUser => userToken.isNotEmpty;
  bool get isAdmin => adminToken.isNotEmpty;

  AuthState copyWith({
    String? userToken,
    String? userId,
    String? username,
    String? adminToken,
    String? adminId,
    String? adminName,
    int? userLoginAt,
    int? adminLoginAt,
  }) {
    return AuthState(
      userToken: userToken ?? this.userToken,
      userId: userId ?? this.userId,
      username: username ?? this.username,
      adminToken: adminToken ?? this.adminToken,
      adminId: adminId ?? this.adminId,
      adminName: adminName ?? this.adminName,
      userLoginAt: userLoginAt ?? this.userLoginAt,
      adminLoginAt: adminLoginAt ?? this.adminLoginAt,
    );
  }

  /// 仅序列化非敏感元数据（用户名、ID、时间戳）。
  Map<String, dynamic> _metaToJson() => {
        'userId': userId,
        'username': username,
        'adminId': adminId,
        'adminName': adminName,
        'userLoginAt': userLoginAt,
        'adminLoginAt': adminLoginAt,
      };

  /// 从存储恢复，并按 1 天有效期裁剪过期的身份。
  /// [meta] 来自 SharedPreferences，[userToken]/[adminToken] 来自 SecureStorage。
  factory AuthState.fromStored({
    required Map<String, dynamic> meta,
    required String userToken,
    required String adminToken,
  }) {
    final now = DateTime.now().millisecondsSinceEpoch;
    final maxMs = kLoginValidity.inMilliseconds;

    int userLoginAt = (meta['userLoginAt'] ?? 0) as int;
    // 超过 1 天 → 视为未登录
    if (userToken.isNotEmpty && (now - userLoginAt) > maxMs) {
      userToken = '';
      userLoginAt = 0;
    }

    int adminLoginAt = (meta['adminLoginAt'] ?? 0) as int;
    if (adminToken.isNotEmpty && (now - adminLoginAt) > maxMs) {
      adminToken = '';
      adminLoginAt = 0;
    }

    return AuthState(
      userToken: userToken,
      userId: userToken.isEmpty ? '' : (meta['userId'] ?? ''),
      username: userToken.isEmpty ? '' : (meta['username'] ?? ''),
      adminToken: adminToken,
      adminId: adminToken.isEmpty ? '' : (meta['adminId'] ?? ''),
      adminName: adminToken.isEmpty ? '' : (meta['adminName'] ?? ''),
      userLoginAt: userLoginAt,
      adminLoginAt: adminLoginAt,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._prefs, AuthState initial) : super(initial);

  final SharedPreferences _prefs;

  static const _keyUserToken = 'user_token';
  static const _keyAdminToken = 'admin_token';

  /// App 启动时调用：同步读取并按有效期裁剪，返回初始状态 + prefs。
  static Future<(SharedPreferences, AuthState)> init() async {
    final prefs = await SharedPreferences.getInstance();

    // 并行读取 secure storage 中的 token
    final (userToken, adminToken) = (
      await _secure.read(key: _keyUserToken) ?? '',
      await _secure.read(key: _keyAdminToken) ?? '',
    );

    // 读取非敏感元数据
    final rawMeta = prefs.getString(_prefsKeyAuthMeta);
    Map<String, dynamic> meta = {};
    if (rawMeta != null) {
      try {
        meta = jsonDecode(rawMeta) as Map<String, dynamic>;
      } catch (_) {}
    }

    final state = AuthState.fromStored(
      meta: meta,
      userToken: userToken,
      adminToken: adminToken,
    );
    return (prefs, state);
  }

  Future<void> _persist() async {
    // 元数据存 SharedPreferences
    await _prefs.setString(_prefsKeyAuthMeta, jsonEncode(state._metaToJson()));
    // Token 存 SecureStorage
    await _secure.write(key: _keyUserToken, value: state.userToken);
    await _secure.write(key: _keyAdminToken, value: state.adminToken);
  }

  Future<void> setUser(String token, String id, String name) async {
    state = state.copyWith(
      userToken: token,
      userId: id,
      username: name,
      userLoginAt: DateTime.now().millisecondsSinceEpoch,
    );
    await _persist();
  }

  Future<void> setAdmin(String token, String id, String name) async {
    state = state.copyWith(
      adminToken: token,
      adminId: id,
      adminName: name,
      adminLoginAt: DateTime.now().millisecondsSinceEpoch,
    );
    await _persist();
  }

  Future<void> logoutUser() async {
    state = state.copyWith(userToken: '', userId: '', username: '', userLoginAt: 0);
    await _secure.delete(key: _keyUserToken);
    await _prefs.setString(_prefsKeyAuthMeta, jsonEncode(state._metaToJson()));
  }

  Future<void> logoutAdmin() async {
    state = state.copyWith(adminToken: '', adminId: '', adminName: '', adminLoginAt: 0);
    await _secure.delete(key: _keyAdminToken);
    await _prefs.setString(_prefsKeyAuthMeta, jsonEncode(state._metaToJson()));
  }
}

/// 在 main() 里用 ProviderScope overrides 注入真实实例。
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => throw UnimplementedError('authProvider must be overridden in main()'),
);
