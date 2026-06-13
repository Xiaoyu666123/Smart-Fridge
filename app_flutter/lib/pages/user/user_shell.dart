import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import 'home_tab.dart';
import 'inventory_tab.dart';
import 'recognize_tab.dart';
import 'chat_tab.dart';
import 'profile_tab.dart';

/// 用户端外壳：底部 5 Tab 导航。
class UserShell extends ConsumerStatefulWidget {
  const UserShell({super.key});

  @override
  ConsumerState<UserShell> createState() => _UserShellState();
}

class _UserShellState extends ConsumerState<UserShell> {
  int _index = 0;

  void _jump(int i) => setState(() => _index = i);

  @override
  Widget build(BuildContext context) {
    final pages = [
      HomeTab(onJumpTab: _jump),
      const InventoryTab(),
      const RecognizeTab(),
      const ChatTab(),
      const ProfileTab(),
    ];

    return Scaffold(
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: _jump,
        backgroundColor: AppColors.bgCard,
        indicatorColor: AppColors.brandPrimaryLight,
        height: 64,
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home, color: AppColors.brandPrimaryDark),
              label: '首页'),
          NavigationDestination(
              icon: Icon(Icons.inventory_2_outlined),
              selectedIcon:
                  Icon(Icons.inventory_2, color: AppColors.brandPrimaryDark),
              label: '库存'),
          NavigationDestination(
              icon: Icon(Icons.camera_alt_outlined),
              selectedIcon:
                  Icon(Icons.camera_alt, color: AppColors.brandPrimaryDark),
              label: '识别'),
          NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline),
              selectedIcon:
                  Icon(Icons.chat_bubble, color: AppColors.brandPrimaryDark),
              label: '食谱'),
          NavigationDestination(
              icon: Icon(Icons.person_outline),
              selectedIcon: Icon(Icons.person, color: AppColors.brandPrimaryDark),
              label: '我的'),
        ],
      ),
    );
  }
}
