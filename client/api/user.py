"""普通用户路由 (/api/v1/user/*)。

仅持有 user token 的会话可访问。
注：管理员账户由 seed/后台管理，不在此处提供注册入口。
"""

import uuid
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    LoginRequest, RegisterRequest, UserTokenResponse, UserInfoResponse,
    InventoryResponse, EventLogResponse,
    ChatRequest, ChatResponse, RecognizeRequest, RecognizeResponse,
    DetectResponse,
    PreferenceResponse, PreferenceAddRequest,
    EnvironmentResponse,
    NotificationResponse, NotificationCountResponse,
    CategoryThresholdResponse,
    SavedRecipeRequest, SavedRecipeResponse,
    CookRecipeRequest, CookRecipeResponse,
    RecipeUpdateRequest,
)
from crud import (
    get_inventory_list, get_inventory_by_id, get_event_logs,
    count_inventory,
    get_preferences_list, add_preference, delete_preference,
    get_conversations, create_user, get_user_by_username,
    get_admin_by_username,
    generate_expiry_notifications, get_user_notifications, get_unread_count,
    mark_notification_read, mark_all_read,
    get_all_thresholds,
    save_recipe, list_saved_recipes, delete_saved_recipe, mark_recipe_cooked,
    update_recipe_meta,
    get_nutrition_report,
    get_cooking_calendar,
    get_user_achievements,
    list_shopping_items, add_shopping_item, update_shopping_item,
    delete_shopping_item, clear_checked_shopping_items, generate_shopping_suggestions,
)
from agents import FridgeAgent
from services.auth import (
    hash_password, verify_password, create_user_token, get_current_user,
    decode_user_token,
)

router = APIRouter(prefix="/user")


# ---- Auth ----

@router.post("/auth/register", response_model=UserTokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # 防止与管理员同名造成混淆
    if get_admin_by_username(db, req.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    if get_user_by_username(db, req.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = create_user(db, req.username, hash_password(req.password))
    token = create_user_token(str(user.id))
    return UserTokenResponse(token=token, user_id=str(user.id), username=user.username)


@router.post("/auth/login", response_model=UserTokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # 拒绝管理员账号通过普通用户入口登录
    if get_admin_by_username(db, req.username):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user = get_user_by_username(db, req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_user_token(str(user.id))
    return UserTokenResponse(token=token, user_id=str(user.id), username=user.username)


@router.get("/auth/me", response_model=UserInfoResponse)
def me(user: User = Depends(get_current_user)):
    return UserInfoResponse(id=str(user.id), username=user.username, created_at=user.created_at)


# ---- Inventory（只读）----

@router.get("/inventory", response_model=list[InventoryResponse])
def list_inventory(
    response: Response,
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    expiring_in_days: Optional[int] = None,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        total = count_inventory(db, device_id=device_id, status=status, category=category,
                                  q=q, start_date=start_date, end_date=end_date,
                                  expiring_in_days=expiring_in_days)
        rows = get_inventory_list(db, device_id=device_id, status=status, category=category,
                                  limit=limit, offset=offset,
                                  q=q, start_date=start_date, end_date=end_date,
                                  expiring_in_days=expiring_in_days)
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存失败: {str(e)}")


@router.get("/inventory/categories")
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        from sqlalchemy import distinct
        from models import Inventory
        rows = db.query(distinct(Inventory.category)).order_by(Inventory.category).all()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询分类列表失败: {str(e)}")


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse)
def get_inventory_detail(inventory_id: uuid.UUID, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存详情失败: {str(e)}")


# ---- Events（只读）----

@router.get("/events", response_model=list[EventLogResponse])
def list_events(
    inventory_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return get_event_logs(db, inventory_id=inventory_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询事件日志失败: {str(e)}")


# ---- Agent ----

@router.get("/agent/conversations")
def list_conversations(limit: int = 100, offset: int = 0, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    try:
        rows = get_conversations(db, str(user.id), limit=limit, offset=offset)
        return [
            {"id": r.id, "role": r.role, "content": r.content,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in reversed(rows)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询对话历史失败: {str(e)}")


@router.post("/agent/chat", response_model=ChatResponse)
def agent_chat(req: ChatRequest, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    try:
        agent = FridgeAgent()
        return agent.chat(db, user_id=str(user.id), message=req.message, city=req.city)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.get("/agent/chat/stream")
def agent_chat_stream(
    message: str,
    token: Optional[str] = None,
    city: Optional[str] = None,
    structured: bool = False,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """SSE 流式对话。

    支持两种 token 传递方式：
    1. 查询参数 ?token=xxx（浏览器 EventSource 使用）
    2. Authorization: Bearer xxx 请求头（移动端使用）
    每个事件 data 是一行 JSON，含 {"type": "delta"|"done", ...}
    structured=true 时使用结构化食谱 prompt（前端按 ===RECIPE=== 块解析卡片）。
    """
    # 优先从 query 参数取，其次从 Authorization Header 取
    raw_token = token
    if not raw_token and authorization:
        raw_token = authorization.replace("Bearer ", "")
    if not raw_token:
        raise HTTPException(status_code=401, detail="缺少登录凭证")
    payload = decode_user_token(raw_token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录凭证无效")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    agent = FridgeAgent()

    def event_generator():
        try:
            for chunk in agent.chat_stream(db, user_id=str(user.id), message=message, city=city,
                                           structured=structured):
                yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
        except Exception as e:
            err = {"type": "error", "message": str(e)}
            yield "data: " + json.dumps(err, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent/recognize", response_model=RecognizeResponse)
def agent_recognize(req: RecognizeRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    try:
        from services.vision import recognize_food
        from services.llm import estimate_freshness, get_season
        from config import settings

        vision_result = recognize_food(req.image)
        category = vision_result["category"]
        confidence = vision_result["confidence"]

        season = get_season()
        freshness = estimate_freshness(category, settings.DEFAULT_CITY, season)

        return RecognizeResponse(
            category=category,
            confidence=confidence,
            shelf_life_days=freshness["shelf_life_days"],
            storage_advice=freshness["storage_advice"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@router.get("/agent/preferences", response_model=list[PreferenceResponse])
def get_user_preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return get_preferences_list(db, str(user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询偏好失败: {str(e)}")


@router.post("/agent/preferences", response_model=PreferenceResponse)
def add_user_preference(req: PreferenceAddRequest, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    try:
        return add_preference(db, user_id=str(user.id),
                              preference_key=req.preference_key,
                              preference_value=req.preference_value)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"添加偏好失败: {str(e)}")


@router.delete("/agent/preferences/{preference_id}")
def delete_user_preference(preference_id: uuid.UUID, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    try:
        pref = delete_preference(db, preference_id)
        if not pref:
            raise HTTPException(status_code=404, detail="偏好记录不存在")
        return {"detail": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除偏好失败: {str(e)}")


# ---- Environment ----

@router.get("/environment", response_model=EnvironmentResponse)
def get_environment(city: Optional[str] = None, user: User = Depends(get_current_user)):
    from config import settings
    from services.weather import get_current_weather

    target = city or settings.DEFAULT_CITY
    try:
        return get_current_weather(target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取环境信息失败: {str(e)}")


# ---- Notifications ----

@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        generate_expiry_notifications(db, user.id)
        return get_user_notifications(db, user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询通知失败: {str(e)}")


@router.get("/notifications/count", response_model=NotificationCountResponse)
def notification_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        generate_expiry_notifications(db, user.id)
        count = get_unread_count(db, user.id)
        return NotificationCountResponse(unread_count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询通知数量失败: {str(e)}")


@router.put("/notifications/{notification_id}/read")
def read_notification(notification_id: uuid.UUID, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    try:
        success = mark_notification_read(db, notification_id, user.id)
        if not success:
            raise HTTPException(status_code=404, detail="通知不存在")
        return {"detail": "已标记已读"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标记已读失败: {str(e)}")


@router.put("/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        count = mark_all_read(db, user.id)
        return {"detail": f"已标记 {count} 条通知为已读"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全部标记已读失败: {str(e)}")


# ---- 类别阈值（只读，用于前端临期判断展示）----

@router.get("/category-thresholds", response_model=list[CategoryThresholdResponse])
def list_thresholds(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return get_all_thresholds(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询阈值失败: {str(e)}")


# ---- 健康饮食报告 ----

@router.get("/stats/nutrition")
def user_stats_nutrition(days: int = 30, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """近 N 天家庭饮食营养结构 + 评分。所有用户共享同一份冰箱数据。"""
    try:
        return get_nutrition_report(db, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询营养报告失败: {str(e)}")


@router.get("/stats/cooking")
def user_stats_cooking(days: int = 365, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """烹饪日历：近 N 天每天打卡过的菜 + 连续打卡天数 + Top 5 最爱做。"""
    try:
        return get_cooking_calendar(db, str(user.id), days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询烹饪日历失败: {str(e)}")


@router.get("/stats/achievements")
def user_stats_achievements(db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    """用户成就墙 + 个人档案 + 近 30 天消耗趋势。"""
    try:
        return get_user_achievements(db, str(user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询成就失败: {str(e)}")


# ---- 购物清单 ----

def _shopping_item_dict(it) -> dict:
    return {
        "id": str(it.id),
        "name": it.name,
        "qty": it.qty,
        "checked": it.checked,
        "source": it.source,
        "created_at": it.created_at.isoformat() if it.created_at else None,
    }


@router.get("/shopping")
def list_shopping(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """购物清单列表。"""
    try:
        rows = list_shopping_items(db, str(user.id))
        items = [_shopping_item_dict(r) for r in rows]
        return {
            "items": items,
            "total": len(items),
            "checked": sum(1 for i in items if i["checked"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询购物清单失败: {str(e)}")


@router.post("/shopping")
def add_shopping(req: dict, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """添加一项。body: {name: str, qty?: int}"""
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name 必填")
    if len(name) > 50:
        raise HTTPException(status_code=400, detail="名称过长（≤50 字）")
    try:
        qty = int(req.get("qty") or 1)
    except (ValueError, TypeError):
        qty = 1
    try:
        it = add_shopping_item(db, str(user.id), name, qty=qty, source="manual")
        return _shopping_item_dict(it)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"添加失败: {str(e)}")


@router.put("/shopping/{item_id}")
def update_shopping(item_id: uuid.UUID, req: dict, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """更新勾选状态 / 数量。body: {checked?: bool, qty?: int}"""
    checked = req.get("checked")
    qty = req.get("qty")
    try:
        qty = int(qty) if qty is not None else None
    except (ValueError, TypeError):
        qty = None
    it = update_shopping_item(db, str(user.id), item_id, checked=checked, qty=qty)
    if not it:
        raise HTTPException(status_code=404, detail="清单项不存在")
    return _shopping_item_dict(it)


@router.delete("/shopping/{item_id}")
def remove_shopping(item_id: uuid.UUID, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if not delete_shopping_item(db, str(user.id), item_id):
        raise HTTPException(status_code=404, detail="清单项不存在")
    return {"detail": "已删除"}


@router.post("/shopping/clear-checked")
def clear_checked_shopping(db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """一键清掉已购买（已勾选）的项。"""
    n = clear_checked_shopping_items(db, str(user.id))
    return {"detail": f"已清除 {n} 项", "removed": n}


@router.post("/shopping/suggest")
def suggest_shopping(db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """让系统根据近期消耗 + 当前库存自动补充建议项到清单。"""
    try:
        added = generate_shopping_suggestions(db, str(user.id), days=30)
        return {
            "added": [_shopping_item_dict(it) for it in added],
            "added_count": len(added),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"生成建议失败: {str(e)}")


@router.get("/agent/coach")
def user_agent_coach(days: int = 30, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """AI 营养教练：基于健康评分 + 偏好 + 临期食材 + 近期消耗，给出本周饮食建议。"""
    from datetime import datetime
    from services.llm import coach_advice
    from crud import get_preferences_list as _get_prefs

    try:
        report = get_nutrition_report(db, days=days)

        # 用户偏好（含 chat 学到的）→ 转成 "key=value" 字符串列表
        pref_rows = _get_prefs(db, str(user.id))
        prefs = [f"{p.preference_value}（{p.preference_key}）" for p in pref_rows]

        # 近期消耗（OUT_PENDING / CONSUMED 的品类频率）
        from models import Inventory
        from datetime import timedelta
        since = datetime.now() - timedelta(days=days)
        rows = (
            db.query(Inventory.category)
            .filter(Inventory.created_at >= since,
                    Inventory.status.in_(["OUT_PENDING", "CONSUMED"]))
            .all()
        )
        from collections import Counter
        recent_consumed = [
            {"category": cat, "count": cnt}
            for cat, cnt in Counter(r[0] for r in rows).most_common(8)
        ]

        # 临期食材
        in_stock_rows = (
            db.query(Inventory)
            .filter(Inventory.status == "IN_STOCK",
                    Inventory.created_at >= datetime.now() - timedelta(days=60))
            .all()
        )
        now = datetime.now()
        expiring = []
        for inv in in_stock_rows:
            md = inv.agent_metadata or {}
            es = md.get("expire_at")
            if not es:
                continue
            try:
                exp = datetime.fromisoformat(es)
            except Exception:
                continue
            d = max(0, (exp - now).days)
            if d <= 4:
                expiring.append({"category": inv.category, "days": d})
        expiring.sort(key=lambda x: x["days"])

        advice = coach_advice(report, prefs, recent_consumed, expiring,
                               user_id=str(user.id))
        return {
            "window_days": days,
            "health": report.get("health_overall"),
            "expiring": expiring[:8],
            "recent_consumed": recent_consumed,
            "advice": advice,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 教练失败: {str(e)}")


@router.post("/agent/substitute")
def user_agent_substitute(req: dict, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """食材替换：让 AI 推荐用什么替代缺失或临期的食材。

    body: {ingredient: str, recipe_name: str (可选)}
    """
    from services.llm import suggest_substitute
    from crud import get_preferences_list as _gp
    from models import Inventory

    ingredient = (req.get("ingredient") or "").strip()
    recipe_name = (req.get("recipe_name") or "").strip()
    if not ingredient:
        raise HTTPException(status_code=400, detail="ingredient 必填")

    try:
        # 当前在库（未过期）食材
        from datetime import datetime
        in_stock = (
            db.query(Inventory)
            .filter(Inventory.status == "IN_STOCK")
            .all()
        )
        now = datetime.now()
        available = []
        for inv in in_stock:
            md = inv.agent_metadata or {}
            es = md.get("expire_at")
            if es:
                try:
                    if datetime.fromisoformat(es) < now:
                        continue   # 跳过已过期的
                except Exception:
                    pass
            if inv.category and inv.category != ingredient:
                available.append(inv.category)

        prefs = [p.preference_value for p in _gp(db, str(user.id))]

        result = suggest_substitute(
            ingredient, recipe_name, available, prefs,
            user_id=str(user.id),
        )
        return {
            "ingredient": ingredient,
            "recipe_name": recipe_name,
            "available_count": len(available),
            **result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 替换建议失败: {str(e)}")


@router.post("/agent/inventory-query")
def user_inventory_query(req: dict, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """自然语言库存问答：用户用自然语言问"我有什么 3 天内过期的肉？"等，
    后端读全量在库库存（含保质期/品牌/状态）让 LLM 据实回答。
    body: {question: str}
    """
    from datetime import datetime
    from services.llm import answer_inventory_query
    from models import Inventory

    question = (req.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 必填")
    if len(question) > 200:
        raise HTTPException(status_code=400, detail="问题过长（≤200 字）")

    try:
        rows = db.query(Inventory).filter(Inventory.status == "IN_STOCK").all()
        now = datetime.now()
        inv = []
        for r in rows:
            md = r.agent_metadata or {}
            es = md.get("expire_at")
            remain_days = None
            if es:
                try:
                    remain_days = (datetime.fromisoformat(es) - now).days
                except Exception:
                    remain_days = None
            ld = r.label_data or {}
            inv.append({
                "category": r.category,
                "status": r.status,
                "remain_days": remain_days,
                "brand": ld.get("brand"),
                "expire_at": es,
            })
        result = answer_inventory_query(question, inv, user_id=str(user.id))
        return {
            "question": question,
            "in_stock_count": len(inv),
            **result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"库存问答失败: {str(e)}")


# 每日小贴士的进程内缓存：{user_id: (date_str, content)}
_daily_tip_cache: dict[str, tuple[str, str]] = {}


@router.get("/agent/daily-tip")
def user_daily_tip(refresh: bool = False, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """每日 AI 一句话。同一天同用户复用缓存，避免重复调 LLM。

    refresh=true 强制重新生成。
    """
    from datetime import datetime, timedelta
    from collections import Counter
    from services.llm import daily_tip
    from services.weather import get_current_weather
    from config import settings as _settings
    from crud import get_preferences_list as _gp, get_nutrition_report
    from models import Inventory

    today_key = datetime.now().strftime("%Y-%m-%d")
    cache_key = str(user.id)
    if not refresh and cache_key in _daily_tip_cache:
        cached_date, cached_text = _daily_tip_cache[cache_key]
        if cached_date == today_key:
            return {"date": today_key, "tip": cached_text, "cached": True}

    try:
        # 天气
        weather = None
        try:
            weather = get_current_weather(_settings.DEFAULT_CITY)
        except Exception:
            pass

        # 临期
        in_stock = (
            db.query(Inventory)
            .filter(Inventory.status == "IN_STOCK")
            .all()
        )
        now = datetime.now()
        expiring = []
        for inv in in_stock:
            md = inv.agent_metadata or {}
            es = md.get("expire_at")
            if not es:
                continue
            try:
                exp = datetime.fromisoformat(es)
            except Exception:
                continue
            d = (exp - now).days
            if 0 <= d <= 4:
                expiring.append({"category": inv.category, "days": max(0, d)})
        expiring.sort(key=lambda x: x["days"])

        # 偏好
        prefs = [p.preference_value for p in _gp(db, str(user.id))][:8]

        # 健康评分
        try:
            report = get_nutrition_report(db, days=14)
            health_score = report.get("health_overall", {}).get("score")
        except Exception:
            health_score = None

        # 近期消耗
        since = now - timedelta(days=14)
        rows = (
            db.query(Inventory.category)
            .filter(Inventory.created_at >= since,
                    Inventory.status.in_(["OUT_PENDING", "CONSUMED"]))
            .all()
        )
        recent_consumed = [
            {"category": cat, "count": cnt}
            for cat, cnt in Counter(r[0] for r in rows).most_common(5)
        ]

        tip = daily_tip(
            weather=weather,
            expiring=expiring,
            preferences=prefs,
            health_score=health_score,
            recent_consumed=recent_consumed,
            user_id=str(user.id),
        )

        _daily_tip_cache[cache_key] = (today_key, tip)
        return {"date": today_key, "tip": tip, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取每日小贴士失败: {str(e)}")


# ---- 食谱收藏 ----

@router.post("/recipes", response_model=SavedRecipeResponse)
def save_recipe_api(req: SavedRecipeRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """收藏一个食谱（前端解析自 LLM 流式输出）。"""
    try:
        data = req.model_dump()
        # ingredients 转纯 dict
        if data.get("ingredients"):
            data["ingredients"] = [
                {"name": i.get("name", ""), "amount": i.get("amount", "")}
                for i in data["ingredients"]
            ]
        rec = save_recipe(db, str(user.id), data)
        return SavedRecipeResponse(
            id=str(rec.id), user_id=rec.user_id, name=rec.name,
            summary=rec.summary, prep_time=rec.prep_time, difficulty=rec.difficulty,
            ingredients=rec.ingredients, steps=rec.steps, tags=rec.tags,
            source=rec.source, cooked_count=rec.cooked_count,
            last_cooked_at=rec.last_cooked_at,
            rating=rec.rating, notes=rec.notes,
            created_at=rec.created_at,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存食谱失败: {str(e)}")


@router.get("/recipes", response_model=list[SavedRecipeResponse])
def list_recipes_api(limit: int = 50, offset: int = 0,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    rows = list_saved_recipes(db, str(user.id), limit=limit, offset=offset)
    return [
        SavedRecipeResponse(
            id=str(r.id), user_id=r.user_id, name=r.name,
            summary=r.summary, prep_time=r.prep_time, difficulty=r.difficulty,
            ingredients=r.ingredients, steps=r.steps, tags=r.tags,
            source=r.source, cooked_count=r.cooked_count,
            last_cooked_at=r.last_cooked_at,
            rating=r.rating, notes=r.notes,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/recipes/{recipe_id}")
def delete_recipe_api(recipe_id: uuid.UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    if not delete_saved_recipe(db, str(user.id), recipe_id):
        raise HTTPException(status_code=404, detail="食谱不存在")
    return {"detail": "已删除"}


@router.put("/recipes/{recipe_id}", response_model=SavedRecipeResponse)
def update_recipe_api(recipe_id: uuid.UUID, req: RecipeUpdateRequest,
                       db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """更新食谱评分 / 笔记。"""
    try:
        r = update_recipe_meta(db, str(user.id), recipe_id,
                                rating=req.rating, notes=req.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not r:
        raise HTTPException(status_code=404, detail="食谱不存在")
    return SavedRecipeResponse(
        id=str(r.id), user_id=r.user_id, name=r.name,
        summary=r.summary, prep_time=r.prep_time, difficulty=r.difficulty,
        ingredients=r.ingredients, steps=r.steps, tags=r.tags,
        source=r.source, cooked_count=r.cooked_count,
        last_cooked_at=r.last_cooked_at,
        rating=r.rating, notes=r.notes,
        created_at=r.created_at,
    )


@router.post("/recipes/{recipe_id}/cook", response_model=CookRecipeResponse)
def cook_recipe_api(recipe_id: uuid.UUID, req: Optional[CookRecipeRequest] = None,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """打卡：标记某个食谱"做过了"。可同时声明用了哪些库存项。

    传入 consumed_inventory_ids 后，对应库存的 status 会改成 OUT_PENDING，
    并写一条 ITEM_OUT 事件日志（与端侧出库流程语义一致），通过 WS 广播给前端。
    """
    consumed_ids = (req.consumed_inventory_ids if req else None) or []
    r, ok_ids, skipped_ids = mark_recipe_cooked(db, str(user.id), recipe_id, consumed_ids)
    if not r:
        raise HTTPException(status_code=404, detail="食谱不存在")

    # WS 广播被消耗的库存
    if ok_ids:
        try:
            from services.ws_events import broadcast_inventory_updated
            from models import Inventory
            for cid in ok_ids:
                inv = db.query(Inventory).filter(Inventory.id == cid).first()
                if inv:
                    broadcast_inventory_updated(inv, source="recipe_cook", prev_status="IN_STOCK")
        except Exception:
            pass

    recipe_resp = SavedRecipeResponse(
        id=str(r.id), user_id=r.user_id, name=r.name,
        summary=r.summary, prep_time=r.prep_time, difficulty=r.difficulty,
        ingredients=r.ingredients, steps=r.steps, tags=r.tags,
        source=r.source, cooked_count=r.cooked_count,
        last_cooked_at=r.last_cooked_at,
        rating=r.rating, notes=r.notes,
        created_at=r.created_at,
    )
    return CookRecipeResponse(
        recipe=recipe_resp,
        consumed_count=len(ok_ids),
        consumed_inventory_ids=ok_ids,
        skipped_inventory_ids=skipped_ids,
    )


# ---- WebSocket 实时通知 ----

@router.websocket("/ws/notifications")
async def ws_notifications(ws: WebSocket, token: str):
    """前端通过 ?token=<user_token> 建立 WS。
    服务端会把"新通知"以 JSON 推过来：
      {"type": "notification.new", "data": {...}}
      {"type": "notification.count", "unread_count": 3}
    """
    from services.ws_manager import manager

    payload = decode_user_token(token)
    if not payload:
        await ws.close(code=4401)
        return
    user_id = payload["sub"]
    await manager.connect(user_id, ws)
    try:
        # 发一条 ready 让前端知道连上了
        await ws.send_json({"type": "ready", "user_id": user_id})
        while True:
            # 客户端可能 ping，服务端就 echo 一下
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"[WS] connection error | user={user_id} | error={e}")
    finally:
        await manager.disconnect(user_id, ws)
