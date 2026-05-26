import type { Node, Edge } from '@vue-flow/core'
import type { TraceStep } from '@/api/trace'
import { toolNameLabels, toolIcons, toolCategoryColors } from './toolConfig'

export interface TraceNodeData {
  step: TraceStep
  label: string
  icon: string
  categoryColor: string
  borderColor: string
  bgColor: string
  [key: string]: unknown
}

function getStatusColors(status: string) {
  if (status === 'SUCCESS') return { borderColor: '#00b42a', bgColor: '#e8f7e8' }
  if (status === 'FAILED') return { borderColor: '#f53f3f', bgColor: '#ffece8' }
  return { borderColor: '#c9cdd4', bgColor: '#f2f3f5' }
}

export function buildTraceFlow(steps: TraceStep[]): {
  nodes: Node<TraceNodeData>[]
  edges: Edge[]
} {
  const NODE_HEIGHT = 90
  const VERTICAL_GAP = 50
  const START_X = 300

  const nodes: Node<TraceNodeData>[] = steps.map((step, i) => {
    const colors = getStatusColors(step.status)
    return {
      id: `step-${step.id}`,
      type: 'traceStep',
      position: { x: START_X, y: i * (NODE_HEIGHT + VERTICAL_GAP) },
      data: {
        step,
        label: toolNameLabels[step.tool_name] || step.tool_name,
        icon: toolIcons[step.tool_name] || 'Cpu',
        categoryColor: toolCategoryColors[step.tool_name] || '#165dff',
        ...colors,
      },
    }
  })

  const edges: Edge[] = steps.slice(0, -1).map((step, i) => ({
    id: `edge-${step.id}-${steps[i + 1].id}`,
    source: `step-${step.id}`,
    target: `step-${steps[i + 1].id}`,
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#165dff', strokeWidth: 2 },
  }))

  return { nodes, edges }
}
