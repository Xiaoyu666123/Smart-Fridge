import 'package:dio/dio.dart';

/// 登录/注册接口封装。传入对应的 Dio 实例。
class AuthApi {
  /// 用户登录：POST /api/v1/user/auth/login
  /// 返回 {token, user_id, username, user_type}
  static Future<Map<String, dynamic>> userLogin(
      Dio userDio, String username, String password) async {
    final res = await userDio.post('/auth/login', data: {
      'username': username,
      'password': password,
    });
    return Map<String, dynamic>.from(res.data);
  }

  /// 用户注册：POST /api/v1/user/auth/register
  static Future<Map<String, dynamic>> userRegister(
      Dio userDio, String username, String password) async {
    final res = await userDio.post('/auth/register', data: {
      'username': username,
      'password': password,
    });
    return Map<String, dynamic>.from(res.data);
  }

  /// 管理员登录：POST /api/v1/admin/auth/login
  /// 返回 {token, admin_id, username, user_type}
  static Future<Map<String, dynamic>> adminLogin(
      Dio adminDio, String username, String password) async {
    final res = await adminDio.post('/auth/login', data: {
      'username': username,
      'password': password,
    });
    return Map<String, dynamic>.from(res.data);
  }
}
