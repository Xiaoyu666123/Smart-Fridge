import userApi from '../userHttp'

export interface LoginRequest {
    username: string
    password: string
}

export interface RegisterRequest {
    username: string
    password: string
}

export interface UserTokenResponse {
    token: string
    user_id: string
    username: string
    user_type: 'user'
}

export function userLogin(data: LoginRequest) {
    return userApi.post<any, UserTokenResponse>('/auth/login', data)
}

export function userRegister(data: RegisterRequest) {
    return userApi.post<any, UserTokenResponse>('/auth/register', data)
}
