"""轻量营养标签：把品类映射到主食/蔬菜/肉/水果/奶/零食/调料 七大类。

不追求精确的营养成分，仅为"健康饮食结构提示"提供大致分布。
词表覆盖中文常见食材的子串模糊匹配。
"""

from typing import Optional


# 关键词 → 营养类别（按优先级匹配，前面的先命中）
NUTRITION_RULES: list[tuple[list[str], str]] = [
    # 蔬菜
    (["菜", "瓜", "茄", "菇", "豆芽", "笋", "韭", "蒜", "葱", "姜", "辣椒", "白菜", "包菜",
      "西兰", "胡萝卜", "番茄", "西红柿", "黄瓜", "土豆", "莴笋", "藕", "萝卜", "生菜",
      "甘蓝", "芹菜", "菠菜", "豆角", "豆苗"], "vegetable"),
    # 水果
    (["果", "苹", "橙", "梨", "桃", "葡萄", "蓝莓", "草莓", "西瓜", "哈密瓜", "芒果",
      "香蕉", "猕猴桃", "柠檬", "橘", "柚", "石榴", "菠萝"], "fruit"),
    # 肉
    (["肉", "牛", "猪", "羊", "鸡", "鸭", "鹅", "排骨", "腿", "翅", "肠", "火腿",
      "培根", "肘", "肝"], "meat"),
    # 鱼海鲜
    (["鱼", "虾", "蟹", "贝", "鱿鱼", "蛤", "蚌", "海鲜", "三文鱼", "金枪鱼"], "seafood"),
    # 蛋奶
    (["蛋", "奶", "酸奶", "奶酪", "黄油", "起司", "酪", "乳"], "dairy_egg"),
    # 主食
    (["米", "面", "馒头", "饺", "包子", "饼", "面包", "意面", "粉", "饭", "面条",
      "燕麦", "玉米", "薯", "粥", "豆腐", "豆制品", "腐竹"], "staple"),
    # 零食/糕点/糖
    (["薯片", "饼干", "蛋糕", "巧克力", "糖", "糖果", "雪糕", "冰淇淋", "果脯", "蜜饯",
      "辣条", "膨化", "曲奇", "果冻"], "snack"),
    # 调料/酱
    (["油", "盐", "酱", "醋", "糖浆", "蜂蜜", "调料", "胡椒", "味精", "鸡精", "豆瓣"], "condiment"),
    # 饮料
    (["饮料", "汽水", "可乐", "咖啡", "茶", "果汁", "酒", "啤酒"], "beverage"),
]


CATEGORY_LABELS: dict[str, dict] = {
    "vegetable":  {"label": "蔬菜",   "emoji": "🥬", "color": "#00b42a", "healthy": True},
    "fruit":      {"label": "水果",   "emoji": "🍎", "color": "#fa8c16", "healthy": True},
    "meat":       {"label": "肉类",   "emoji": "🍗", "color": "#f53f3f", "healthy": False},
    "seafood":    {"label": "海鲜",   "emoji": "🐟", "color": "#06b6d4", "healthy": True},
    "dairy_egg":  {"label": "蛋奶",   "emoji": "🥚", "color": "#fadb14", "healthy": True},
    "staple":     {"label": "主食",   "emoji": "🍚", "color": "#7c4dff", "healthy": False},
    "snack":      {"label": "零食",   "emoji": "🍫", "color": "#eb2f96", "healthy": False},
    "condiment":  {"label": "调料",   "emoji": "🧂", "color": "#86909c", "healthy": False},
    "beverage":   {"label": "饮料",   "emoji": "🥤", "color": "#13c2c2", "healthy": False},
    "other":      {"label": "其他",   "emoji": "📦", "color": "#86909c", "healthy": True},
}


def classify(category: Optional[str]) -> str:
    """把 category 名字映射到营养类别（vegetable / fruit / meat / ...）。"""
    if not category:
        return "other"
    name = category.lower()
    for keywords, tag in NUTRITION_RULES:
        for kw in keywords:
            if kw.lower() in name or kw in category:
                return tag
    return "other"


def get_category_info(tag: str) -> dict:
    return CATEGORY_LABELS.get(tag, CATEGORY_LABELS["other"])


def assess_health(distribution: dict[str, int]) -> dict:
    """根据分布给出整体健康评分 + 改进建议。

    distribution: {tag: count}
    返回 {score: 0-100, level: 'good'|'fair'|'poor', tips: [..]}
    """
    total = sum(distribution.values()) or 1
    veg = distribution.get("vegetable", 0)
    fruit = distribution.get("fruit", 0)
    meat = distribution.get("meat", 0)
    seafood = distribution.get("seafood", 0)
    snack = distribution.get("snack", 0)
    beverage = distribution.get("beverage", 0)
    staple = distribution.get("staple", 0)
    dairy = distribution.get("dairy_egg", 0)

    veg_fruit_ratio = (veg + fruit) / total
    meat_ratio = (meat + seafood) / total
    snack_ratio = (snack + beverage) / total

    # 评分起点 70，三大维度加减分
    score = 70

    tips: list[str] = []

    if veg_fruit_ratio >= 0.4:
        score += 15
    elif veg_fruit_ratio >= 0.25:
        score += 5
    else:
        score -= 10
        tips.append(f"蔬菜水果占比仅 {round(veg_fruit_ratio * 100)}%，建议提升到 40% 以上")

    if 0.15 <= meat_ratio <= 0.35:
        score += 10
    elif meat_ratio > 0.35:
        score -= 8
        tips.append(f"肉类占比 {round(meat_ratio * 100)}%，可适当多吃些蔬菜替代")
    else:
        tips.append("蛋白质来源较少，可补充些鱼禽蛋")

    if snack_ratio > 0.15:
        score -= 10
        tips.append(f"零食/饮料占比 {round(snack_ratio * 100)}%，建议减少")

    if dairy < 1 and total > 5:
        tips.append("没有蛋奶类，可适量加点")

    score = max(0, min(100, score))

    if score >= 80:
        level = "good"
    elif score >= 60:
        level = "fair"
    else:
        level = "poor"

    if not tips:
        tips.append("饮食结构均衡，继续保持 👍")

    return {
        "score": score,
        "level": level,
        "tips": tips,
        "veg_fruit_ratio": round(veg_fruit_ratio, 3),
        "meat_ratio": round(meat_ratio, 3),
        "snack_ratio": round(snack_ratio, 3),
    }
