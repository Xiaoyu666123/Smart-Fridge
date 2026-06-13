import userApi from '../userHttp'

export interface EnvironmentInfo {
    city: string
    region: string | null
    temperature: number | null
    feels_like: number | null
    humidity: number | null
    wind_speed: number | null
    wind_dir: string | null
    weather_code: string | null
    weather_desc: string
    cloudcover: number | null
    visibility: number | null
    pressure: number | null
    precip: number | null
    uv_index: number | null
    season: string
    sunrise: string | null
    sunset: string | null
    updated_at: string
}

export function getEnvironment(city?: string) {
    return userApi.get<any, EnvironmentInfo>('/environment', { params: city ? { city } : {} })
}
