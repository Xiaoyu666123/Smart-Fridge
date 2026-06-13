import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'core/auth_store.dart';
import 'core/dio_client.dart' show navigatorKey;
import 'pages/login_page.dart';
import 'pages/user/user_shell.dart';
import 'pages/admin/admin_shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    navigatorKey: navigatorKey,
    initialLocation: '/login',
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final loc = state.matchedLocation;

      // 登录页：已登录则跳到对应主页（管理员优先）
      if (loc == '/login') {
        if (auth.isAdmin) return '/admin';
        if (auth.isUser) return '/user';
        return null;
      }
      // 管理端需 admin token
      if (loc.startsWith('/admin') && !auth.isAdmin) return '/login';
      // 用户端需 user token
      if (loc.startsWith('/user') && !auth.isUser) return '/login';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (c, s) => const LoginPage()),
      GoRoute(path: '/user', builder: (c, s) => const UserShell()),
      GoRoute(path: '/admin', builder: (c, s) => const AdminShell()),
    ],
    errorBuilder: (c, s) => const Scaffold(
      body: Center(child: Text('页面不存在')),
    ),
  );
});
