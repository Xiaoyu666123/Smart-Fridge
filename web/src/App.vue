<script setup lang="ts">
import CommandPalette from '@/components/CommandPalette.vue'
import QuickRecognizeFAB from '@/components/QuickRecognizeFAB.vue'
import RouteProgressBar from '@/components/RouteProgressBar.vue'
</script>

<template>
  <RouteProgressBar />
  <router-view />
  <!-- 全局命令面板（Ctrl+K / Cmd+K 唤起；Ctrl+/ 看帮助）-->
  <CommandPalette />
  <!-- 全局快速识别浮动面板（admin 端）-->
  <QuickRecognizeFAB />
</template>
