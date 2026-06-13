import userApi from '../userHttp'

export interface NotificationItem {
    id: string
    user_id: string
    type: string
    title: string
    content: string
    related_item_id: string | null
    is_read: boolean
    created_at: string | null
}

export interface NotificationCount {
    unread_count: number
}

export function getNotifications() {
    return userApi.get<any, NotificationItem[]>('/notifications')
}

export function getNotificationCount() {
    return userApi.get<any, NotificationCount>('/notifications/count')
}

export function markAsRead(notificationId: string) {
    return userApi.put<any, { detail: string }>(`/notifications/${notificationId}/read`)
}

export function markAllAsRead() {
    return userApi.put<any, { detail: string }>('/notifications/read-all')
}
