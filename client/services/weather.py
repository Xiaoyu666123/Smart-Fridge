import httpx
from datetime import datetime

WTTR_URL = "https://wttr.in"

WTTR_CODES = {
    "113": "晴", "116": "大部晴", "119": "多云", "122": "阴",
    "143": "雾", "176": "局部小雨", "179": "局部小雪",
    "200": "雷阵雨", "227": "吹雪", "230": "暴风雪",
    "248": "冻雾", "260": "冻雾", "263": "毛毛雨",
    "266": "毛毛雨", "281": "冻毛毛雨", "284": "大冻毛毛雨",
    "293": "小雨", "296": "小雨", "299": "中雨",
    "302": "中雨", "305": "大雨", "308": "暴雨",
    "311": "冻雨", "314": "大冻雨", "317": "雨夹雪",
    "320": "大雨夹雪", "323": "小雪", "326": "小雪",
    "329": "中雪", "332": "中雪", "335": "大雪",
    "338": "暴雪", "350": "冰粒", "353": "小阵雨",
    "356": "大阵雨", "359": "暴雨", "362": "小雨夹雪",
    "365": "雨夹雪", "368": "小阵雪", "371": "大阵雪",
    "374": "冰粒", "377": "大冰粒",
    "386": "雷阵雨", "389": "强雷暴", "392": "雷阵雪",
    "395": "强雷暴伴雪",
}


def _map_weather(code: str) -> str:
    return WTTR_CODES.get(code, "未知")


def _get_season() -> str:
    month = datetime.now().month
    if month in (3, 4, 5):
        return "春季"
    elif month in (6, 7, 8):
        return "夏季"
    elif month in (9, 10, 11):
        return "秋季"
    else:
        return "冬季"


def get_current_weather(city: str) -> dict:
    resp = httpx.get(
        f"{WTTR_URL}/{city}",
        params={"format": "j1"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    cc = data["current_condition"][0]
    area = data.get("nearest_area", [{}])[0]
    weather = data.get("weather", [{}])[0]
    astro = weather.get("astronomy", [{}])[0] if weather else {}

    city_name = area.get("areaName", [{}])[0].get("value", city)
    region = area.get("region", [{}])[0].get("value", "")
    weather_code = cc.get("weatherCode", "113")
    temp = float(cc["temp_C"])
    humidity = float(cc["humidity"])
    feels_like = float(cc["FeelsLikeC"])
    wind_speed = float(cc["windspeedKmph"])
    wind_dir = cc.get("winddir16Point", "")
    cloudcover = float(cc.get("cloudcover", 0))
    visibility = float(cc.get("visibility", 0))
    pressure = float(cc.get("pressure", 0))
    precip = float(cc.get("precipMM", 0))
    uv_index = float(cc.get("uvIndex", 0))

    return {
        "city": city_name,
        "region": region,
        "temperature": temp,
        "feels_like": feels_like,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_dir": wind_dir,
        "weather_code": weather_code,
        "weather_desc": _map_weather(weather_code),
        "cloudcover": cloudcover,
        "visibility": visibility,
        "pressure": pressure,
        "precip": precip,
        "uv_index": uv_index,
        "season": _get_season(),
        "sunrise": astro.get("sunrise", ""),
        "sunset": astro.get("sunset", ""),
        "updated_at": datetime.now().isoformat(),
    }
