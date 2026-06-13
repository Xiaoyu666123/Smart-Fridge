import adminApi from '../adminHttp'

export interface AdminUserItem {
    id: string
    username: string
    created_at: string | null
    inventory_count: number
    preference_count: number
    conversation_count: number
}

export function listUsers(search?: string) {
    return adminApi.get<any, AdminUserItem[]>('/users', { params: search ? { search } : {} })
}

export function createUser(data: { username: string; password: string }) {
    return adminApi.post<any, AdminUserItem>('/users', data)
}

export function resetUserPassword(userId: string, newPassword: string) {
    return adminApi.put<any, { detail: string }>(`/users/${userId}/password`, { new_password: newPassword })
}

export function deleteUser(userId: string) {
    return adminApi.delete<any, { detail: string }>(`/users/${userId}`)
}

export function changeAdminPassword(oldPassword: string, newPassword: string) {
    return adminApi.post<any, { detail: string }>('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
    })
}
