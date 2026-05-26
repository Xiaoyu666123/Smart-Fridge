import api from './index'

export interface InventoryItem {
  id: string
  device_id: string
  category: string
  status: string
  remain_ratio: number
  bbox: number[] | null
  agent_metadata: Record<string, any> | null
  snapshot_path: string | null
  created_at: string | null
  update_at: string | null
  stored_at: string | null
}

export interface InventoryCreateData {
  device_id: string
  category: string
  status?: string
  remain_ratio?: number
  bbox?: number[] | null
  agent_metadata?: Record<string, any> | null
  snapshot_path?: string | null
}

export interface InventoryUpdateData {
  category?: string
  status?: string
  remain_ratio?: number
  bbox?: number[] | null
  agent_metadata?: Record<string, any> | null
  snapshot_path?: string | null
}

export function getInventoryList(params?: { device_id?: string; status?: string; category?: string }) {
  return api.get<any, InventoryItem[]>('/inventory', { params })
}

export function getCategories() {
  return api.get<any, string[]>('/inventory/categories')
}

export function createInventory(data: InventoryCreateData) {
  return api.post<any, InventoryItem>('/inventory', data)
}

export function updateInventory(id: string, data: InventoryUpdateData) {
  return api.put<any, InventoryItem>(`/inventory/${id}`, data)
}

export function deleteInventory(id: string) {
  return api.delete<any, { detail: string }>(`/inventory/${id}`)
}

export function uploadInventoryImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<any, { snapshot_path: string; url: string }>('/inventory/upload-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
