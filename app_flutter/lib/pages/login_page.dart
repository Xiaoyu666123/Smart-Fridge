import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../core/theme.dart';
import '../core/auth_store.dart';
import '../core/dio_client.dart';
import '../api/auth_api.dart';

enum LoginMode { userLogin, userRegister, adminLogin }

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  LoginMode _mode = LoginMode.userLogin;
  final _userCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  bool _loading = false;
  bool _obscure = true;

  bool get _isAdmin => _mode == LoginMode.adminLogin;

  @override
  void dispose() {
    _userCtrl.dispose();
    _pwdCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  void _switchMode(LoginMode m) {
    setState(() {
      _mode = m;
      _userCtrl.clear();
      _pwdCtrl.clear();
      _confirmCtrl.clear();
    });
  }

  void _toast(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: error ? AppColors.danger : AppColors.success,
      behavior: SnackBarBehavior.floating,
    ));
  }

  Future<void> _submit() async {
    final username = _userCtrl.text.trim();
    final password = _pwdCtrl.text;
    if (username.isEmpty || password.isEmpty) {
      _toast('请输入用户名和密码', error: true);
      return;
    }
    if (_mode == LoginMode.userRegister) {
      if (username.length < 3) return _toast('用户名至少3个字符', error: true);
      if (password.length < 6) return _toast('密码至少6个字符', error: true);
      if (password != _confirmCtrl.text) return _toast('两次密码不一致', error: true);
    }

    setState(() => _loading = true);
    try {
      if (_mode == LoginMode.adminLogin) {
        final dio = ref.read(adminDioProvider);
        final r = await AuthApi.adminLogin(dio, username, password);
        await ref.read(authProvider.notifier).setAdmin(
            r['token'], r['admin_id']?.toString() ?? '', r['username'] ?? username);
        _toast('登录成功');
        if (mounted) context.go('/admin');
      } else if (_mode == LoginMode.userLogin) {
        final dio = ref.read(userDioProvider);
        final r = await AuthApi.userLogin(dio, username, password);
        await ref.read(authProvider.notifier).setUser(
            r['token'], r['user_id']?.toString() ?? '', r['username'] ?? username);
        _toast('登录成功');
        if (mounted) context.go('/user');
      } else {
        final dio = ref.read(userDioProvider);
        final r = await AuthApi.userRegister(dio, username, password);
        await ref.read(authProvider.notifier).setUser(
            r['token'], r['user_id']?.toString() ?? '', r['username'] ?? username);
        _toast('注册成功');
        if (mounted) context.go('/user');
      }
    } catch (e) {
      _toast(extractError(e, '登录失败'), error: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final accent = _isAdmin ? AppColors.brandSecondary : AppColors.brandPrimary;
    return Scaffold(
      backgroundColor: AppColors.bgColor,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Container(
              constraints: const BoxConstraints(maxWidth: 420),
              padding: const EdgeInsets.all(28),
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderColor),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x0F1B1F24),
                    blurRadius: 24,
                    offset: Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // 品牌
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.kitchen_rounded, color: accent, size: 34),
                      const SizedBox(width: 10),
                      Text('SMART-FRIDGE',
                          style: TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.w800,
                              color: accent,
                              letterSpacing: 1)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  const Text('智能冰箱食材管理系统',
                      style: TextStyle(
                          fontSize: 13, color: AppColors.textSecondary)),
                  const SizedBox(height: 24),

                  // 三 tab
                  _buildTabs(accent),
                  const SizedBox(height: 22),

                  if (_isAdmin) _adminBadge(),

                  // 用户名
                  TextField(
                    controller: _userCtrl,
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.person_outline),
                      hintText: _isAdmin
                          ? '管理员账号'
                          : (_mode == LoginMode.userRegister
                              ? '用户名（至少3个字符）'
                              : '用户名'),
                    ),
                  ),
                  const SizedBox(height: 14),
                  // 密码
                  TextField(
                    controller: _pwdCtrl,
                    obscureText: _obscure,
                    onSubmitted: (_) =>
                        _mode == LoginMode.userRegister ? null : _submit(),
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.lock_outline),
                      hintText: _mode == LoginMode.userRegister
                          ? '密码（至少6个字符）'
                          : '密码',
                      suffixIcon: IconButton(
                        icon: Icon(_obscure
                            ? Icons.visibility_off
                            : Icons.visibility),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                  ),
                  if (_mode == LoginMode.userRegister) ...[
                    const SizedBox(height: 14),
                    TextField(
                      controller: _confirmCtrl,
                      obscureText: _obscure,
                      onSubmitted: (_) => _submit(),
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.lock_outline),
                        hintText: '确认密码',
                      ),
                    ),
                  ],
                  const SizedBox(height: 22),

                  // 提交按钮
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _loading ? null : _submit,
                      style: ElevatedButton.styleFrom(backgroundColor: accent),
                      child: _loading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2.4, color: Colors.white))
                          : Text(_submitLabel()),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  String _submitLabel() {
    switch (_mode) {
      case LoginMode.userLogin:
        return '登录';
      case LoginMode.userRegister:
        return '注册';
      case LoginMode.adminLogin:
        return '管理员登录';
    }
  }

  Widget _buildTabs(Color accent) {
    Widget tab(String label, LoginMode m) {
      final active = _mode == m;
      return Expanded(
        child: GestureDetector(
          onTap: () => _switchMode(m),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: active ? accent : Colors.transparent,
                  width: 2,
                ),
              ),
            ),
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                fontWeight: active ? FontWeight.w600 : FontWeight.w500,
                color: active ? accent : AppColors.textSecondary,
              ),
            ),
          ),
        ),
      );
    }

    return Container(
      decoration: const BoxDecoration(
        border: Border(
            bottom: BorderSide(color: Color(0xFFF0F0F0), width: 2)),
      ),
      child: Row(
        children: [
          tab('用户登录', LoginMode.userLogin),
          tab('用户注册', LoginMode.userRegister),
          tab('管理员登录', LoginMode.adminLogin),
        ],
      ),
    );
  }

  Widget _adminBadge() {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.brandSecondaryLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFFED7AA)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.lock, size: 14, color: AppColors.brandSecondary),
          const SizedBox(width: 6),
          Text('管理员入口，仅授权账户可登录',
              style: TextStyle(
                  fontSize: 13, color: AppColors.brandSecondary)),
        ],
      ),
    );
  }
}
