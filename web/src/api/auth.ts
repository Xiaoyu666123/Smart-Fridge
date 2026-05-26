import api from './index'

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
}

export interface TokenResponse {
  token: string
  user_id: string
  username: string
  role: string
}

export interface UserInfo {
  id: string
  username: string
  role: string
  created_at: string | null
}

export function login(data: LoginRequest) {
  return api.post<any, TokenResponse>('/auth/login', data)
}

export function register(data: RegisterRequest) {
  return api.post<any, TokenResponse>('/auth/register', data)
}

export function getMe() {
  return api.get<any, UserInfo>('/auth/me')
}
