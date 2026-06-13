<script setup lang="ts">
/**
 * 工具链可视化 —— 深色「神经管线」风格（HTML5 Canvas 2D）。
 *
 * 设计目标：展示级高级感，而非教学播放器。
 *  - 始终深色科技底（深空蓝渐变 + 浮动氛围粒子 + 微光网格）
 *  - 横向流动管线布局，节点轻微上下错落，像数据在管道里流动
 *  - 节点：玻璃拟态卡片 + 分类色辉光 + emoji 光圈 + 呼吸微动
 *  - 连线：A→B 渐变贝塞尔，多个发光光点持续奔流（数据流动感）
 *  - 悬停放大发光、点击弹详情；拖拽 / 平移 / 缩放 / 双击适应
 */
import { ref, watch, onMounted, onBeforeUnmount, reactive } from 'vue'
import type { TraceStep } from '@/api/admin/trace'
import {
  toolNameLabels, toolDescriptions, getToolCategory, getToolEmoji,
} from '@/utils/toolConfig'

const props = defineProps<{ steps: TraceStep[] }>()

// ---- 布局参数 ----
const NODE_W = 196
const NODE_H = 88
const GAP_X = 96
const ZIGZAG = 40        // 上下错落幅度
const PAD = 80

const canvasRef = ref<HTMLCanvasElement>()
const wrapRef = ref<HTMLDivElement>()
let ctx: CanvasRenderingContext2D | null = null
let raf = 0
let dpr = 1
let t0 = performance.now()
let appearT0 = performance.now()    // 入场动画起点
const APPEAR_DUR = 0.42             // 单节点入场时长(s)
const APPEAR_STAGGER = 0.10         // 节点间错峰(s)

const view = reactive({ x: 0, y: 0, scale: 1 })

// 鼠标视差（屏幕中心归一化偏移）
let parallax = { x: 0, y: 0 }
let parallaxTarget = { x: 0, y: 0 }

interface Node {
  step: TraceStep
  idx: number
  x: number
  y: number
  color: string
  emoji: string
  label: string
  desc: string
}
let nodes: Node[] = []

// 氛围粒子
interface Particle { x: number; y: number; vx: number; vy: number; r: number; a: number }
let ambient: Particle[] = []

let hoverId: number | null = null
const selected = ref<TraceStep | null>(null)
let draggingNode: Node | null = null
let dragOff = { x: 0, y: 0 }
let panning = false
let panStart = { x: 0, y: 0, vx: 0, vy: 0 }
let movedDist = 0

// ---- 布局：横向错落管线 ----
function buildNodes() {
  const cy = 260
  nodes = props.steps.map((s, i) => {
    const cat = getToolCategory(s.tool_name)
    const offset = i % 2 === 0 ? -ZIGZAG : ZIGZAG
    return {
      step: s,
      idx: i,
      x: PAD + i * (NODE_W + GAP_X),
      y: cy + offset,
      color: cat.color,
      emoji: getToolEmoji(s.tool_name),
      label: toolNameLabels[s.tool_name] || s.tool_name,
      desc: toolDescriptions[s.tool_name] || '',
    }
  })
}

function buildAmbient() {
  ambient = []
  for (let i = 0; i < 36; i++) {
    ambient.push({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00006,
      vy: (Math.random() - 0.5) * 0.00006,
      r: Math.random() * 1.6 + 0.4,
      a: Math.random() * 0.4 + 0.1,
    })
  }
}

function contentBounds() {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const n of nodes) {
    minX = Math.min(minX, n.x); minY = Math.min(minY, n.y)
    maxX = Math.max(maxX, n.x + NODE_W); maxY = Math.max(maxY, n.y + NODE_H)
  }
  if (!isFinite(minX)) return { x: 0, y: 0, w: 600, h: 400 }
  return { x: minX - PAD, y: minY - PAD, w: (maxX - minX) + PAD * 2, h: (maxY - minY) + PAD * 2 }
}

// ---- 坐标转换 ----
function toWorld(cx: number, cy: number) {
  const r = canvasRef.value!.getBoundingClientRect()
  const px = parallax.x * 18
  const py = parallax.y * 18
  return { x: (cx - r.left - view.x - px) / view.scale, y: (cy - r.top - view.y - py) / view.scale }
}

function nodeAt(wx: number, wy: number): Node | null {
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i]
    if (wx >= n.x && wx <= n.x + NODE_W && wy >= n.y && wy <= n.y + NODE_H) return n
  }
  return null
}

function roundRect(c: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  c.beginPath()
  c.moveTo(x + r, y)
  c.arcTo(x + w, y, x + w, y + h, r)
  c.arcTo(x + w, y + h, x, y + h, r)
  c.arcTo(x, y + h, x, y, r)
  c.arcTo(x, y, x + w, y, r)
  c.closePath()
}

function cubic(p0: number, p1: number, p2: number, p3: number, t: number) {
  const mt = 1 - t
  return mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3
}

function hexA(hex: string, a: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${a})`
}

function fmt(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function truncate(c: CanvasRenderingContext2D, text: string, maxW: number): string {
  if (c.measureText(text).width <= maxW) return text
  let s = text
  while (s.length > 1 && c.measureText(s + '…').width > maxW) s = s.slice(0, -1)
  return s + '…'
}

// 节点入场进度 [0,1]，依次错峰浮现
function appearProgress(i: number): number {
  const elapsed = (performance.now() - appearT0) / 1000
  const local = (elapsed - i * APPEAR_STAGGER) / APPEAR_DUR
  if (local <= 0) return 0
  if (local >= 1) return 1
  // easeOutBack 轻微回弹
  const x = local
  const c1 = 1.70158, c3 = c1 + 1
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2)
}

function easeOutCubic(x: number): number {
  return 1 - Math.pow(1 - x, 3)
}

// 悬停时的"关联路径"高亮：返回该节点链路上需要点亮的节点 index 集合
function highlightSet(): Set<number> | null {
  if (hoverId === null && selected.value === null) return null
  const targetId = hoverId !== null ? hoverId : selected.value!.id
  const idx = nodes.findIndex(n => n.step.id === targetId)
  if (idx < 0) return null
  // 链式：高亮前一个、自己、后一个（上下游邻接）
  const s = new Set<number>()
  s.add(idx)
  if (idx > 0) s.add(idx - 1)
  if (idx < nodes.length - 1) s.add(idx + 1)
  return s
}

// ---- 绘制 ----
function draw() {
  if (!ctx || !canvasRef.value) return
  const time = (performance.now() - t0) / 1000
  const cw = canvasRef.value.clientWidth
  const ch = canvasRef.value.clientHeight
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cw, ch)

  // —— 深空背景渐变 ——
  const bg = ctx.createLinearGradient(0, 0, cw, ch)
  bg.addColorStop(0, '#0a1424')
  bg.addColorStop(0.5, '#0c1a2e')
  bg.addColorStop(1, '#0a1220')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, cw, ch)

  // 角落辉光
  const glow1 = ctx.createRadialGradient(cw * 0.15, ch * 0.1, 0, cw * 0.15, ch * 0.1, cw * 0.5)
  glow1.addColorStop(0, 'rgba(14,165,233,0.10)')
  glow1.addColorStop(1, 'rgba(14,165,233,0)')
  ctx.fillStyle = glow1
  ctx.fillRect(0, 0, cw, ch)
  const glow2 = ctx.createRadialGradient(cw * 0.85, ch * 0.9, 0, cw * 0.85, ch * 0.9, cw * 0.5)
  glow2.addColorStop(0, 'rgba(99,102,241,0.10)')
  glow2.addColorStop(1, 'rgba(99,102,241,0)')
  ctx.fillStyle = glow2
  ctx.fillRect(0, 0, cw, ch)

  // —— 缓动极光带 ——
  ctx.save()
  ctx.globalCompositeOperation = 'lighter'
  const auroras = [
    { c: '14,165,233', base: 0.30, amp: 0.10, speed: 0.18, phase: 0 },
    { c: '99,102,241', base: 0.55, amp: 0.12, speed: 0.13, phase: 2 },
    { c: '15,198,194', base: 0.72, amp: 0.09, speed: 0.22, phase: 4 },
  ]
  for (const a of auroras) {
    const yc = ch * (a.base + Math.sin(time * a.speed + a.phase) * a.amp)
    const g = ctx.createLinearGradient(0, yc - 120, 0, yc + 120)
    g.addColorStop(0, `rgba(${a.c},0)`)
    g.addColorStop(0.5, `rgba(${a.c},0.07)`)
    g.addColorStop(1, `rgba(${a.c},0)`)
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.moveTo(0, yc)
    const segs = 6
    for (let i = 0; i <= segs; i++) {
      const x = (cw / segs) * i
      const y = yc + Math.sin(time * a.speed * 1.6 + i * 0.9 + a.phase) * 36
      ctx.lineTo(x, y)
    }
    ctx.lineTo(cw, yc + 130)
    ctx.lineTo(0, yc + 130)
    ctx.closePath()
    ctx.fill()
  }
  ctx.restore()

  // 氛围粒子（屏幕空间）
  for (const p of ambient) {
    p.x += p.vx; p.y += p.vy
    if (p.x < 0) p.x = 1; if (p.x > 1) p.x = 0
    if (p.y < 0) p.y = 1; if (p.y > 1) p.y = 0
    const flick = 0.5 + 0.5 * Math.sin(time * 1.5 + p.x * 30)
    ctx.fillStyle = `rgba(120,180,240,${p.a * flick})`
    ctx.beginPath()
    ctx.arc(p.x * cw, p.y * ch, p.r, 0, Math.PI * 2)
    ctx.fill()
  }

  // —— 进入世界坐标 ——
  // 鼠标视差平滑趋近
  parallax.x += (parallaxTarget.x - parallax.x) * 0.06
  parallax.y += (parallaxTarget.y - parallax.y) * 0.06
  const px = parallax.x * 18
  const py = parallax.y * 18
  ctx.translate(view.x + px, view.y + py)
  ctx.scale(view.scale, view.scale)

  // 计算高亮集合
  const hl = highlightSet()

  // 微光点阵网格
  const gridStep = 40
  const b = contentBounds()
  ctx.fillStyle = 'rgba(120,160,220,0.05)'
  for (let gx = b.x; gx < b.x + b.w; gx += gridStep) {
    for (let gy = b.y; gy < b.y + b.h; gy += gridStep) {
      ctx.beginPath()
      ctx.arc(gx, gy, 1, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // —— 连线 + 流动光点 ——
  for (let i = 0; i < nodes.length - 1; i++) {
    const a = nodes[i], b2 = nodes[i + 1]
    // 入场：两端节点都浮现后才画线
    const apA = appearProgress(i), apB = appearProgress(i + 1)
    const edgeAppear = Math.min(apA, apB)
    if (edgeAppear <= 0.01) continue
    // 该边是否在高亮路径上（i 与 i+1 都在集合里）
    const dim = hl ? !(hl.has(i) && hl.has(i + 1)) : false

    const ax = a.x + NODE_W, ay = a.y + NODE_H / 2     // 右中
    const bx = b2.x, by = b2.y + NODE_H / 2            // 左中
    const c1x = ax + GAP_X * 0.6, c1y = ay
    const c2x = bx - GAP_X * 0.6, c2y = by

    ctx.globalAlpha = (dim ? 0.18 : 1) * easeOutCubic(edgeAppear)

    // 渐变描边
    const grad = ctx.createLinearGradient(ax, ay, bx, by)
    grad.addColorStop(0, hexA(a.color, 0.7))
    grad.addColorStop(1, hexA(b2.color, 0.7))
    ctx.strokeStyle = grad
    ctx.lineWidth = dim ? 1.5 : 2
    ctx.shadowColor = hexA(a.color, 0.5)
    ctx.shadowBlur = dim ? 2 : 8
    ctx.beginPath()
    ctx.moveTo(ax, ay)
    ctx.bezierCurveTo(c1x, c1y, c2x, c2y, bx, by)
    ctx.stroke()
    ctx.shadowBlur = 0

    // 多个流动光点（高亮路径上更亮更多）
    const SPARKS = dim ? 2 : 3
    for (let s = 0; s < SPARKS; s++) {
      const tt = ((time * (dim ? 0.3 : 0.45) + i * 0.25 + s / SPARKS) % 1)
      const ppx = cubic(ax, c1x, c2x, bx, tt)
      const ppy = cubic(ay, c1y, c2y, by, tt)
      const fade = Math.sin(tt * Math.PI)
      ctx.fillStyle = hexA(b2.color, (dim ? 0.4 : 0.9) * fade)
      ctx.shadowColor = b2.color
      ctx.shadowBlur = dim ? 4 : 10
      ctx.beginPath()
      ctx.arc(ppx, ppy, dim ? 1.8 : 2.6, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
    }
    ctx.globalAlpha = 1
  }

  // —— 节点 ——
  nodes.forEach((n, i) => {
    const ap = appearProgress(i)
    if (ap <= 0.01) return
    const hovered = hoverId === n.step.id
    const isSel = selected.value?.id === n.step.id
    const active = hovered || isSel
    const dim = hl ? !hl.has(i) : false
    const breathe = 0.5 + 0.5 * Math.sin(time * 1.4 + i * 0.7)
    const failed = n.step.status === 'FAILED'

    // 入场：缩放 + 上浮 + 透明
    const ease = easeOutCubic(Math.min(1, ap))
    const appearScale = 0.6 + 0.4 * Math.min(1, ap)   // ap 可能 >1（回弹），裁到 1
    const appearDy = (1 - ease) * 24

    ctx!.save()
    ctx!.globalAlpha = (dim ? 0.32 : 1) * ease

    // 以节点中心做入场缩放
    const ncx = n.x + NODE_W / 2, ncy = n.y + NODE_H / 2 + appearDy
    ctx!.translate(ncx, ncy)
    ctx!.scale(appearScale, appearScale)
    ctx!.translate(-ncx, -ncy)

    const ox = n.x, oy = n.y + appearDy

    // 外辉光
    ctx!.shadowColor = failed ? 'rgba(245,63,63,0.6)' : hexA(n.color, active ? 0.9 : 0.4 + breathe * 0.2)
    ctx!.shadowBlur = active ? 34 : (dim ? 6 : 16 + breathe * 6)

    // 卡片玻璃底
    roundRect(ctx!, ox, oy, NODE_W, NODE_H, 16)
    const cardGrad = ctx!.createLinearGradient(ox, oy, ox, oy + NODE_H)
    cardGrad.addColorStop(0, 'rgba(28,42,64,0.95)')
    cardGrad.addColorStop(1, 'rgba(18,30,48,0.95)')
    ctx!.fillStyle = cardGrad
    ctx!.fill()
    ctx!.shadowBlur = 0

    // 顶部高光描边
    roundRect(ctx!, ox, oy, NODE_W, NODE_H, 16)
    ctx!.lineWidth = active ? 2 : 1.2
    ctx!.strokeStyle = failed ? 'rgba(245,63,63,0.7)' : hexA(n.color, active ? 1 : 0.55)
    ctx!.stroke()

    // 左侧竖向能量条
    ctx!.save()
    roundRect(ctx!, ox, oy, NODE_W, NODE_H, 16)
    ctx!.clip()
    const barGrad = ctx!.createLinearGradient(ox, oy, ox, oy + NODE_H)
    barGrad.addColorStop(0, hexA(n.color, 0.9))
    barGrad.addColorStop(1, hexA(n.color, 0.5))
    ctx!.fillStyle = barGrad
    ctx!.fillRect(ox, oy, 5, NODE_H)
    ctx!.restore()

    // emoji 光圈
    const ix = ox + 32, iy = oy + NODE_H / 2
    ctx!.beginPath()
    ctx!.arc(ix, iy, 19, 0, Math.PI * 2)
    ctx!.fillStyle = hexA(n.color, 0.16)
    ctx!.fill()
    ctx!.lineWidth = 1.4
    ctx!.strokeStyle = hexA(n.color, 0.6)
    ctx!.stroke()
    ctx!.font = '19px serif'
    ctx!.textAlign = 'center'
    ctx!.textBaseline = 'middle'
    ctx!.fillText(n.emoji, ix, iy + 1)

    // 序号徽标
    ctx!.beginPath()
    ctx!.arc(ox + 16, oy + 15, 9, 0, Math.PI * 2)
    ctx!.fillStyle = n.color
    ctx!.fill()
    ctx!.fillStyle = '#fff'
    ctx!.font = 'bold 11px sans-serif'
    ctx!.fillText(String(i + 1), ox + 16, oy + 16)

    // 标题
    ctx!.textAlign = 'left'
    ctx!.textBaseline = 'alphabetic'
    ctx!.fillStyle = '#eaf2fb'
    ctx!.font = 'bold 14px sans-serif'
    ctx!.fillText(truncate(ctx!, n.label, NODE_W - 70), ox + 58, oy + 38)

    // 状态点 + 耗时
    const stColor = failed ? '#ff6b6b' : (n.step.status === 'SUCCESS' ? '#3ee089' : '#9aa7b8')
    ctx!.beginPath()
    ctx!.arc(ox + 61, oy + 56, 3.5, 0, Math.PI * 2)
    ctx!.fillStyle = stColor
    ctx!.shadowColor = stColor
    ctx!.shadowBlur = 6
    ctx!.fill()
    ctx!.shadowBlur = 0
    ctx!.fillStyle = 'rgba(180,196,216,0.85)'
    ctx!.font = '11px sans-serif'
    const statusText = n.step.status === 'SUCCESS' ? '成功'
      : failed ? '失败' : (n.step.status || '跳过')
    ctx!.fillText(`${statusText} · ${fmt(n.step.duration_ms)}`, ox + 70, oy + 60)

    ctx!.restore()
  })

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function loop() {
  draw()
  raf = requestAnimationFrame(loop)
}

function resize() {
  const cv = canvasRef.value
  if (!cv) return
  dpr = window.devicePixelRatio || 1
  cv.width = cv.clientWidth * dpr
  cv.height = cv.clientHeight * dpr
  ctx = cv.getContext('2d')
}

function fitView() {
  const cv = canvasRef.value
  if (!cv || nodes.length === 0) return
  const b = contentBounds()
  const w = cv.clientWidth, h = cv.clientHeight
  const s = Math.min(1.4, Math.max(0.3, Math.min((w - 30) / b.w, (h - 30) / b.h)))
  view.scale = s
  view.x = (w - b.w * s) / 2 - b.x * s
  view.y = (h - b.h * s) / 2 - b.y * s
}

function zoom(factor: number) {
  const cv = canvasRef.value
  if (!cv) return
  const w = cv.clientWidth / 2, h = cv.clientHeight / 2
  const ns = Math.min(2, Math.max(0.3, view.scale * factor))
  const cx = (w - view.x) / view.scale
  const cy = (h - view.y) / view.scale
  view.scale = ns
  view.x = w - cx * ns
  view.y = h - cy * ns
}

// ---- 交互 ----
function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  movedDist = 0
  const w = toWorld(e.clientX, e.clientY)
  const n = nodeAt(w.x, w.y)
  if (n) {
    draggingNode = n
    dragOff = { x: w.x - n.x, y: w.y - n.y }
  } else {
    panning = true
    panStart = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }
  }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  if (draggingNode) {
    const w = toWorld(e.clientX, e.clientY)
    draggingNode.x = w.x - dragOff.x
    draggingNode.y = w.y - dragOff.y
    movedDist++
  } else if (panning) {
    view.x = panStart.vx + (e.clientX - panStart.x)
    view.y = panStart.vy + (e.clientY - panStart.y)
    movedDist++
  }
}

function onMouseUp() {
  if (draggingNode && movedDist < 3) selected.value = draggingNode.step
  draggingNode = null
  panning = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

function onHover(e: MouseEvent) {
  const r = canvasRef.value!.getBoundingClientRect()
  // 鼠标视差：相对中心归一化 [-1,1]
  parallaxTarget.x = ((e.clientX - r.left) / r.width - 0.5) * 2
  parallaxTarget.y = ((e.clientY - r.top) / r.height - 0.5) * 2
  const w = toWorld(e.clientX, e.clientY)
  const n = nodeAt(w.x, w.y)
  hoverId = n ? n.step.id : null
  if (canvasRef.value) canvasRef.value.style.cursor = n ? 'pointer' : (panning ? 'grabbing' : 'grab')
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const cv = canvasRef.value!
  const r = cv.getBoundingClientRect()
  const mx = e.clientX - r.left, my = e.clientY - r.top
  const ns = Math.min(2, Math.max(0.3, view.scale * (e.deltaY > 0 ? 0.92 : 1.08)))
  const cx = (mx - view.x) / view.scale
  const cy = (my - view.y) / view.scale
  view.scale = ns
  view.x = mx - cx * ns
  view.y = my - cy * ns
}

function resetLayout() {
  buildNodes()
  fitView()
  selected.value = null
}

let ro: ResizeObserver | null = null

watch(() => props.steps, () => {
  buildNodes()
  fitView()
  appearT0 = performance.now()
  selected.value = null
}, { deep: true })

onMounted(() => {
  resize()
  buildNodes()
  buildAmbient()
  fitView()
  appearT0 = performance.now()
  loop()
  ro = new ResizeObserver(() => resize())
  if (wrapRef.value) ro.observe(wrapRef.value)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  if (ro) ro.disconnect()
})

function statusColor(status: string): string {
  if (status === 'FAILED') return '#ff6b6b'
  if (status === 'SUCCESS') return '#3ee089'
  return '#9aa7b8'
}
</script>

<template>
  <div ref="wrapRef" class="c2d-wrap">
    <canvas
      ref="canvasRef"
      class="c2d-canvas"
      @mousedown="onMouseDown"
      @mousemove="onHover"
      @wheel="onWheel"
      @dblclick="fitView"
    ></canvas>

    <!-- 工具栏 -->
    <div class="c2d-toolbar">
      <button class="c2d-btn" title="适应窗口" @click="fitView"><el-icon><Aim /></el-icon></button>
      <button class="c2d-btn" title="放大" @click="zoom(1.2)"><el-icon><ZoomIn /></el-icon></button>
      <button class="c2d-btn" title="缩小" @click="zoom(1/1.2)"><el-icon><ZoomOut /></el-icon></button>
      <button class="c2d-btn" title="重置" @click="resetLayout"><el-icon><Refresh /></el-icon></button>
      <span class="c2d-zoom">{{ Math.round(view.scale * 100) }}%</span>
    </div>

    <div class="c2d-hint">拖拽节点 · 拖空白平移 · 滚轮缩放 · 点节点看详情</div>

    <!-- 详情面板 -->
    <transition name="slide">
      <div v-if="selected" class="c2d-detail" @mousedown.stop @wheel.stop>
        <div class="c2d-detail-head">
          <span class="c2d-detail-title">
            {{ getToolEmoji(selected.tool_name) }}
            {{ toolNameLabels[selected.tool_name] || selected.tool_name }}
          </span>
          <el-icon class="c2d-detail-close" @click="selected = null"><Close /></el-icon>
        </div>
        <div class="c2d-detail-body">
          <p v-if="toolDescriptions[selected.tool_name]" class="c2d-detail-desc">
            {{ toolDescriptions[selected.tool_name] }}
          </p>
          <div class="c2d-detail-stats">
            <div class="c2d-stat">
              <div class="c2d-stat-label">状态</div>
              <div class="c2d-stat-value" :style="{ color: statusColor(selected.status) }">{{ selected.status }}</div>
            </div>
            <div class="c2d-stat">
              <div class="c2d-stat-label">耗时</div>
              <div class="c2d-stat-value">{{ fmt(selected.duration_ms) }}</div>
            </div>
          </div>
          <div class="c2d-detail-section">
            <div class="c2d-detail-label">输入</div>
            <pre v-if="selected.tool_input" class="c2d-json">{{ JSON.stringify(selected.tool_input, null, 2) }}</pre>
            <span v-else class="c2d-json-empty">无</span>
          </div>
          <div class="c2d-detail-section">
            <div class="c2d-detail-label">输出</div>
            <pre v-if="selected.tool_output" class="c2d-json">{{ JSON.stringify(selected.tool_output, null, 2) }}</pre>
            <span v-else class="c2d-json-empty">无</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.c2d-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 540px;
  overflow: hidden;
  border-radius: var(--radius-md);
}

.c2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

/* 工具栏（深色玻璃） */
.c2d-toolbar {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: rgba(20, 32, 50, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(120, 160, 220, 0.18);
  border-radius: 999px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.c2d-btn {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #aebfd4;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.c2d-btn:hover {
  background: rgba(14, 165, 233, 0.25);
  color: #7fd4ff;
}

.c2d-zoom {
  font-size: 12px;
  font-weight: 600;
  color: #aebfd4;
  min-width: 38px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.c2d-hint {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  padding: 5px 14px;
  background: rgba(20, 32, 50, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(120, 160, 220, 0.15);
  border-radius: 999px;
  font-size: 11px;
  color: rgba(174, 191, 212, 0.8);
  pointer-events: none;
  white-space: nowrap;
}

/* 详情面板（深色玻璃） */
.c2d-detail {
  position: absolute;
  top: 0;
  right: 0;
  width: 360px;
  max-width: 82%;
  height: 100%;
  background: rgba(14, 24, 40, 0.92);
  backdrop-filter: blur(14px);
  border-left: 1px solid rgba(120, 160, 220, 0.2);
  box-shadow: -8px 0 28px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  z-index: 10;
}

.c2d-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(120, 160, 220, 0.15);
}

.c2d-detail-title {
  font-size: 15px;
  font-weight: 700;
  color: #eaf2fb;
}

.c2d-detail-close {
  cursor: pointer;
  color: #8ea1bb;
  font-size: 18px;
}

.c2d-detail-close:hover { color: #fff; }

.c2d-detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}

.c2d-detail-desc {
  font-size: 13px;
  color: #b4c4d8;
  line-height: 1.6;
  margin: 0 0 14px;
  padding: 10px 12px;
  background: rgba(120, 160, 220, 0.08);
  border-radius: 8px;
  border-left: 3px solid #0ea5e9;
}

.c2d-detail-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}

.c2d-stat {
  background: rgba(120, 160, 220, 0.07);
  border-radius: 10px;
  padding: 10px 12px;
}

.c2d-stat-label {
  font-size: 11px;
  color: #8ea1bb;
  margin-bottom: 4px;
}

.c2d-stat-value {
  font-size: 14px;
  font-weight: 700;
  color: #eaf2fb;
}

.c2d-detail-section { margin-bottom: 14px; }

.c2d-detail-label {
  font-size: 12px;
  font-weight: 600;
  color: #8ea1bb;
  margin-bottom: 6px;
}

.c2d-json {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(8, 16, 28, 0.6);
  border: 1px solid rgba(120, 160, 220, 0.12);
  font-size: 11.5px;
  line-height: 1.55;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: #c8d6e8;
}

.c2d-json-empty {
  font-size: 12px;
  color: #6b7c93;
}

.slide-enter-active, .slide-leave-active { transition: transform 0.25s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }
</style>
