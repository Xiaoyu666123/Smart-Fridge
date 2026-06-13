import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 配色：克制中性 + 单一品牌点缀。追求"设计过"的成品感，而非高饱和拼色。
class AppColors {
  // 品牌主色：沉稳一点的蓝（比纯亮天青蓝更耐看，用于点缀而非大面积填充）
  static const brandPrimary = Color(0xFF1573B8);
  static const brandPrimaryHover = Color(0xFF2E8FD0);
  static const brandPrimaryDark = Color(0xFF0F567F);
  static const brandPrimaryLight = Color(0xFFDCEBF6);
  static const brandPrimarySoft = Color(0xFFF0F6FB);

  // 管理员辅助色：低饱和琥珀，不刺眼
  static const brandSecondary = Color(0xFFB4690E);
  static const brandSecondaryHover = Color(0xFFCB7C1E);
  static const brandSecondaryLight = Color(0xFFF6ECDD);

  // 状态色（柔和版）
  static const success = Color(0xFF2E9E6B);
  static const warning = Color(0xFFC98A1E);
  static const danger = Color(0xFFD2503F);
  static const info = Color(0xFF5566B5);

  // 中性背景 / 文字
  static const bgColor = Color(0xFFF5F6F8);
  static const bgCard = Color(0xFFFFFFFF);
  static const bgSoft = Color(0xFFEEF0F3);
  static const textPrimary = Color(0xFF1B1F24);
  static const textSecondary = Color(0xFF5B6573);
  static const textPlaceholder = Color(0xFF9AA2AD);
  static const borderColor = Color(0xFFE7E9ED);
}

class AppTheme {
  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.brandPrimary,
        primary: AppColors.brandPrimary,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: AppColors.bgColor,
    );
    return base.copyWith(
      // 纯白顶栏 + 深色标题，左对齐，底部一条发丝线靠 surfaceTint 关闭
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.bgCard,
        foregroundColor: AppColors.textPrimary,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: AppColors.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
        iconTheme: IconThemeData(color: AppColors.textPrimary),
        systemOverlayStyle: SystemUiOverlayStyle.dark,
      ),
      cardTheme: CardThemeData(
        color: AppColors.bgCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.borderColor),
        ),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.borderColor,
        thickness: 1,
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bgCard,
        hintStyle: const TextStyle(color: AppColors.textPlaceholder),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderColor),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.borderColor),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: AppColors.brandPrimary, width: 1.5),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.brandPrimary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(vertical: 13),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.bgCard,
        elevation: 0,
        height: 62,
        surfaceTintColor: Colors.transparent,
        indicatorColor: AppColors.brandPrimaryLight,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            fontSize: 11,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
            color: selected ? AppColors.brandPrimaryDark : AppColors.textSecondary,
          );
        }),
      ),
    );
  }

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.brandPrimary,
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: const Color(0xFF12161C),
    );
  }
}
