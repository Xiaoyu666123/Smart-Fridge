import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import 'dashboard_tab.dart';
import 'admin_inventory_tab.dart';
import 'devices_tab.dart';
import 'admin_more_tab.dart';

/// 管理端外壳：底部 4 Tab（珊瑚橙主题）。
class AdminShell extends ConsumerStatefulWidget {
  const AdminShell({super.key});

  @override
  ConsumerState<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends ConsumerState<AdminShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final pages = const [
      DashboardTab(),
      AdminInventoryTab(),
      DevicesTab(),
      AdminMoreTab(),
    ];

    return Scaffold(
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.dashboard_outlined),
              selectedIcon: Icon(Icons.dashboard, color: AppColors.brandPrimaryDark),
              label: '大盘'),
          NavigationDestination(
              icon: Icon(Icons.inventory_2_outlined),
              selectedIcon:
                  Icon(Icons.inventory_2, color: AppColors.brandPrimaryDark),
              label: '库存'),
          NavigationDestination(
              icon: Icon(Icons.devices_outlined),
              selectedIcon: Icon(Icons.devices, color: AppColors.brandPrimaryDark),
              label: '设备'),
          NavigationDestination(
              icon: Icon(Icons.menu),
              selectedIcon: Icon(Icons.menu_open, color: AppColors.brandPrimaryDark),
              label: '更多'),
        ],
      ),
    );
  }
}
