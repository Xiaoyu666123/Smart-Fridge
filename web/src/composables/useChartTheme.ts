/**
 * 让 echarts 跟随全局明/暗主题。
 * 使用：
 *   const chartTheme = useChartTheme()
 *   <v-chart :theme="chartTheme" :option="..." autoresize />
 *
 * 这里不真的注册 echarts 主题，只是返回 'dark' / 'default' 字符串，
 * vue-echarts 会用对应主题渲染（'dark' 是 echarts 内置主题）。
 */
import { computed } from 'vue'
import { useThemeStore } from '@/stores/theme'

export function useChartTheme() {
    const theme = useThemeStore()
    return computed(() => (theme.isDark ? 'dark' : 'default'))
}
