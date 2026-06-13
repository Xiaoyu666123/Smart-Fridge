<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getEnvironment, type EnvironmentInfo } from '@/api/user/environment'

const loading = ref(false)
const envInfo = ref<EnvironmentInfo | null>(null)
const city = ref('')

async function fetchEnvironment() {
  loading.value = true
  try {
    envInfo.value = await getEnvironment(city.value || undefined)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const weatherIcon = computed(() => {
  const code = envInfo.value?.weather_code
  if (!code) return 'Sunny'
  const n = parseInt(code)
  if (n === 113) return 'Sunny'
  if (n === 116) return 'PartlyCloudy'
  if (n <= 122) return 'Cloudy'
  if (n <= 176) return 'Drizzle'
  if (n <= 230) return 'Lightning'
  if (n <= 266) return 'Drizzle'
  if (n <= 320) return 'Rainy'
  if (n <= 338) return 'Snowy'
  if (n <= 377) return 'Rainy'
  return 'Lightning'
})

const tempColor = computed(() => {
  const t = envInfo.value?.temperature
  if (t === null || t === undefined) return '#165dff'
  if (t <= 0) return '#3b82f6'
  if (t <= 15) return '#06b6d4'
  if (t <= 25) return '#00b42a'
  if (t <= 35) return '#ff7d00'
  return '#f53f3f'
})

const humColor = computed(() => {
  const h = envInfo.value?.humidity
  if (h === null || h === undefined) return '#165dff'
  if (h <= 30) return '#ff7d00'
  if (h <= 60) return '#00b42a'
  if (h <= 80) return '#06b6d4'
  return '#3b82f6'
})

function getUvLevel(uv: number | null): { label: string; color: string } {
  if (uv === null || uv === undefined) return { label: '--', color: '#999' }
  if (uv <= 2) return { label: '低', color: '#00b42a' }
  if (uv <= 5) return { label: '中等', color: '#ff7d00' }
  if (uv <= 7) return { label: '高', color: '#f53f3f' }
  if (uv <= 10) return { label: '很高', color: '#c9302c' }
  return { label: '极高', color: '#7b1fa2' }
}

onMounted(fetchEnvironment)
</script>

<template>
  <div>
    <!-- 查询栏 -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <el-form :inline="true">
        <el-form-item label="城市">
          <el-input v-model="city" placeholder="输入城市名称，如：广东江门" clearable style="width: 220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchEnvironment" :loading="loading">查询天气</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-if="envInfo">
      <!-- 天气概览 -->
      <el-card shadow="never" class="hero-card">
        <div class="hero-bg" :style="{ background: `linear-gradient(135deg, ${tempColor}18, ${tempColor}08)` }">
          <div class="hero-content">
            <div class="hero-left">
              <el-icon :size="72" :style="{ color: tempColor }">
                <component :is="weatherIcon" />
              </el-icon>
              <div class="hero-temp-group">
                <div class="hero-temp">
                  <span class="temp-num">{{ envInfo.temperature ?? '--' }}</span>
                  <span class="temp-unit">°C</span>
                </div>
                <div class="hero-feels">体感 {{ envInfo.feels_like ?? '--' }}°C</div>
              </div>
            </div>
            <div class="hero-right">
              <div class="hero-city">{{ envInfo.city }}</div>
              <div class="hero-region" v-if="envInfo.region">{{ envInfo.region }}</div>
              <div class="hero-desc">
                <el-tag :style="{ background: tempColor, color: '#fff', border: 'none' }" round>
                  {{ envInfo.weather_desc }}
                </el-tag>
                <el-tag type="info" round style="margin-left: 8px">{{ envInfo.season }}</el-tag>
              </div>
              <div class="hero-meta">
                <span><el-icon><Sunny /></el-icon> {{ envInfo.sunrise || '--' }}</span>
                <span><el-icon><Moon /></el-icon> {{ envInfo.sunset || '--' }}</span>
              </div>
              <div class="hero-update">更新于 {{ new Date(envInfo.updated_at).toLocaleString('zh-CN') }}</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 详细指标 -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon" :style="{ background: tempColor + '1a', color: tempColor }">
            <el-icon :size="26"><Sunny /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.temperature ?? '--' }}°C</div>
            <div class="metric-label">温度</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: Math.min(100, Math.max(0, ((envInfo.temperature ?? 0) + 10) / 55 * 100)) + '%', background: tempColor }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" :style="{ background: humColor + '1a', color: humColor }">
            <el-icon :size="26"><Cloudy /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.humidity ?? '--' }}%</div>
            <div class="metric-label">湿度</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: (envInfo.humidity ?? 0) + '%', background: humColor }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" style="background: #e8f0ff; color: #165dff">
            <el-icon :size="26"><WindPower /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.wind_speed ?? '--' }} km/h</div>
            <div class="metric-label">风速 {{ envInfo.wind_dir || '' }}</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: Math.min(100, (envInfo.wind_speed ?? 0) / 100 * 100) + '%', background: '#165dff' }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" style="background: #f0e8ff; color: #722ed1">
            <el-icon :size="26"><View /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.visibility ?? '--' }} km</div>
            <div class="metric-label">能见度</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: Math.min(100, (envInfo.visibility ?? 0) / 20 * 100) + '%', background: '#722ed1' }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" :style="{ background: getUvLevel(envInfo.uv_index).color + '1a', color: getUvLevel(envInfo.uv_index).color }">
            <el-icon :size="26"><Sunny /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.uv_index ?? '--' }}</div>
            <div class="metric-label">UV 指数 · {{ getUvLevel(envInfo.uv_index).label }}</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: Math.min(100, (envInfo.uv_index ?? 0) / 11 * 100) + '%', background: getUvLevel(envInfo.uv_index).color }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" style="background: #e8f7e8; color: #00b42a">
            <el-icon :size="26"><Cloudy /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.cloudcover ?? '--' }}%</div>
            <div class="metric-label">云量</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: (envInfo.cloudcover ?? 0) + '%', background: '#00b42a' }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" style="background: #e8f4ff; color: #0fc6c2">
            <el-icon :size="26"><Coffee /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.pressure ?? '--' }} hPa</div>
            <div class="metric-label">气压</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: Math.min(100, Math.max(0, ((envInfo.pressure ?? 1000) - 950) / 100 * 100)) + '%', background: '#0fc6c2' }"></div></div>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-icon" style="background: #e8f0ff; color: #3491fa">
            <el-icon :size="26"><Coffee /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ envInfo.precip ?? 0 }} mm</div>
            <div class="metric-label">降水量</div>
          </div>
          <div class="metric-bar">
            <div class="bar-track"><div class="bar-fill" :style="{ width: Math.min(100, (envInfo.precip ?? 0) / 10 * 100) + '%', background: '#3491fa' }"></div></div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="!envInfo && !loading" description="请查询城市查看天气" />
  </div>
</template>

<style scoped>
.hero-card {
  margin-bottom: 20px;
  overflow: hidden;
}

.hero-card :deep(.el-card__body) {
  padding: 0;
}

.hero-bg {
  padding: 32px 36px;
  border-radius: var(--radius-md);
}

.hero-content {
  display: flex;
  align-items: center;
  gap: 48px;
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.hero-temp-group {
  display: flex;
  flex-direction: column;
}

.hero-temp {
  display: flex;
  align-items: baseline;
  line-height: 1;
}

.temp-num {
  font-size: 64px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -2px;
}

.temp-unit {
  font-size: 28px;
  font-weight: 300;
  color: var(--text-secondary);
  margin-left: 2px;
}

.hero-feels {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 6px;
}

.hero-right {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hero-city {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.hero-region {
  font-size: 14px;
  color: var(--text-secondary);
}

.hero-desc {
  display: flex;
  align-items: center;
  margin-top: 4px;
}

.hero-meta {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.hero-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.hero-update {
  font-size: 12px;
  color: var(--text-placeholder);
  margin-top: 2px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.metric-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow 0.2s, transform 0.2s;
}

.metric-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.metric-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-body {
  display: flex;
  flex-direction: column;
}

.metric-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.metric-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.bar-track {
  height: 4px;
  background: var(--bg-color);
  border-radius: 2px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s ease;
}

@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero-content {
    flex-direction: column;
    gap: 20px;
  }
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
