import userApi from '../userHttp'

export interface ShoppingItem {
    id: string
    name: string
    qty: number
    checked: boolean
    source: 'auto' | 'manual'
    created_at: string | null
}

export interface ShoppingList {
    items: ShoppingItem[]
    total: number
    checked: number
}

export function getShoppingList() {
    return userApi.get<any, ShoppingList>('/shopping')
}

export function addShoppingItem(name: string, qty = 1) {
    return userApi.post<any, ShoppingItem>('/shopping', { name, qty })
}

export function updateShoppingItem(id: string, data: { checked?: boolean; qty?: number }) {
    return userApi.put<any, ShoppingItem>(`/shopping/${id}`, data)
}

export function deleteShoppingItem(id: string) {
    return userApi.delete<any, { detail: string }>(`/shopping/${id}`)
}

export function clearCheckedShopping() {
    return userApi.post<any, { detail: string; removed: number }>('/shopping/clear-checked', {})
}

export function suggestShopping() {
    return userApi.post<any, { added: ShoppingItem[]; added_count: number }>('/shopping/suggest', {})
}
