import adminApi from '../adminHttp'

export interface LoginRequest {
    username: string
    password: string
}

export interface AdminTokenResponse {
    token: string
    admin_id: string
    username: string
    user_type: 'admin'
}

export function adminLogin(data: LoginRequest) {
    return adminApi.post<any, AdminTokenResponse>('/auth/login', data)
}
