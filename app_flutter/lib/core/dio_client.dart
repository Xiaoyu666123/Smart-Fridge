import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'config.dart';
import 'auth_store.dart';

/// 全局 Navigator Key，用于在 Dio 拦截器中触发路由跳转。
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

/// 用户端 Dio：baseURL = /api/v1/user，自动带 user token。
final userDioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.userBase,
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 60),
  ));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      final token = ref.read(authProvider).userToken;
      if (token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    },
    onError: (e, handler) {
      if (e.response?.statusCode == 401) {
        ref.read(authProvider.notifier).logoutUser();
        _navigateToLogin();
      }
      handler.next(e);
    },
  ));
  return dio;
});

/// 管理端 Dio：baseURL = /api/v1/admin，自动带 admin token。
final adminDioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.adminBase,
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 120),
  ));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      final token = ref.read(authProvider).adminToken;
      if (token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    },
    onError: (e, handler) {
      if (e.response?.statusCode == 401) {
        ref.read(authProvider.notifier).logoutAdmin();
        _navigateToLogin();
      }
      handler.next(e);
    },
  ));
  return dio;
});

/// 401 时跳转到登录页（清除所有路由栈）。
void _navigateToLogin() {
  final ctx = navigatorKey.currentContext;
  if (ctx != null) {
    GoRouter.of(ctx).go('/login');
  }
}

/// 从 DioException 提取后端的 detail 错误信息。
String extractError(Object e, [String fallback = '请求失败']) {
  if (e is DioException) {
    final data = e.response?.data;
    if (data is Map && data['detail'] != null) {
      return data['detail'].toString();
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.connectionError) {
      return '连接后端失败，请检查网络或后端地址';
    }
    return e.message ?? fallback;
  }
  return fallback;
}
