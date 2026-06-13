import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme.dart';
import 'core/auth_store.dart';
import 'router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // 启动前同步加载本地登录状态（按 1 天有效期裁剪），避免冷启动竞态导致误跳登录页。
  final (prefs, initialAuth) = await AuthNotifier.init();

  runApp(
    ProviderScope(
      overrides: [
        authProvider.overrideWith((ref) => AuthNotifier(prefs, initialAuth)),
      ],
      child: const SmartFridgeApp(),
    ),
  );
}

class SmartFridgeApp extends ConsumerWidget {
  const SmartFridgeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: '智能冰箱',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.light,
      routerConfig: router,
    );
  }
}
