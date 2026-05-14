"""策略组页面路由 Blueprint — 策略发现、我的策略、事件详情、管理员页面"""
import logging

from flask import (
    Blueprint,
    redirect,
    render_template,
    session,
)

from compass.data.database import Database
from compass.strategy import db

logger = logging.getLogger("compass.strategy.routes.pages")

bp = Blueprint("strategy_pages", __name__)


def _require_login():
    """检查登录状态，未登录重定向到 /login"""
    uid = session.get("uid")
    if not uid:
        return None
    return uid


def _is_admin():
    """检查当前用户是否为管理员"""
    uid = session.get("uid")
    if not uid:
        return False
    try:
        with Database() as dbobj:
            _, user = dbobj.select_one(
                "SELECT is_admin FROM user WHERE id = %s", (uid,)
            )
            return user and user.get("is_admin") == 1
    except Exception:
        return False


def _get_user_info():
    """获取当前用户基本信息"""
    uid = session.get("uid")
    name = session.get("name", "")
    return {
        "uid": uid,
        "name": name,
        "is_admin": _is_admin(),
    }


# ---------------------------------------------------------------------------
# 策略发现页
# ---------------------------------------------------------------------------


@bp.route("/strategy/discover/")
def discover():
    uid = _require_login()
    if uid is None:
        return redirect("/login")

    # 获取 active 策略组并附带订阅状态
    groups = db.list_strategy_groups_with_subscription(uid, status="active")

    # 统计
    total_groups = len(groups)
    subscribed_count = sum(1 for g in groups if g.get("subscribed"))

    # 活跃事件数
    open_events = 0
    try:
        result = db.query_group_events(status="open", limit=1, offset=0)
        open_events = result.get("total", 0)
    except Exception:
        pass

    user = _get_user_info()
    return render_template(
        "strategy/discover.html",
        groups=groups,
        stats={
            "total_groups": total_groups,
            "subscribed_count": subscribed_count,
            "open_events": open_events,
        },
        user=user,
        is_admin=user["is_admin"],
    )


# ---------------------------------------------------------------------------
# 我的策略页
# ---------------------------------------------------------------------------


@bp.route("/strategy/my/")
def my_strategies():
    uid = _require_login()
    if uid is None:
        return redirect("/login")

    # 查询用户订阅
    subscriptions = db.list_user_subscriptions(uid)

    # 为每个订阅的策略组查询 open 事件
    strategy_events = []
    for sub in subscriptions:
        gid = sub["strategy_group_id"]
        try:
            evt_result = db.query_group_events(
                strategy_group_id=gid, status="open", limit=50, offset=0
            )
            events = evt_result.get("items", [])
        except Exception:
            events = []
        strategy_events.append(
            {
                "subscription": sub,
                "events": events,
            }
        )

    user = _get_user_info()
    return render_template(
        "strategy/my_strategies.html",
        strategy_events=strategy_events,
        user=user,
        is_admin=user["is_admin"],
    )


# ---------------------------------------------------------------------------
# 事件详情页
# ---------------------------------------------------------------------------


@bp.route("/strategy/events/<int:event_id>/")
def event_detail(event_id):
    uid = _require_login()
    if uid is None:
        return redirect("/login")

    event = db.get_group_event(event_id)
    if not event:
        return render_template("strategy/404.html", message="事件不存在"), 404

    # 获取策略组名称
    group = db.get_strategy_group(event["strategy_group_id"])
    group_name = group.get("name", "") if group else ""

    # 计算持续天数
    import datetime
    created_at = event.get("created_at")
    if created_at:
        if isinstance(created_at, str):
            try:
                created_at = datetime.datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = None
        if created_at:
            days = (datetime.datetime.now() - created_at).days + 1
        else:
            days = 0
    else:
        days = 0

    # 注入 strategy_name 到 event 对象，供模板直接引用
    event["strategy_name"] = group_name

    user = _get_user_info()
    return render_template(
        "strategy/event_detail.html",
        event=event,
        group_name=group_name,
        duration_days=days,
        user=user,
        is_admin=user["is_admin"],
    )


# ---------------------------------------------------------------------------
# 管理员策略列表页
# ---------------------------------------------------------------------------


@bp.route("/strategy/admin/groups/")
def admin_list():
    uid = _require_login()
    if uid is None:
        return redirect("/login")
    if not _is_admin():
        return redirect("/login")

    groups = db.list_strategy_groups()

    # 为每个策略组附加订阅人数
    for g in groups:
        g["subscriber_count"] = db.count_subscribers(g["id"])

    user = _get_user_info()
    return render_template(
        "strategy/admin_list.html",
        groups=groups,
        user=user,
        is_admin=user["is_admin"],
    )


# ---------------------------------------------------------------------------
# 管理员策略编辑/创建页
# ---------------------------------------------------------------------------


@bp.route("/strategy/admin/groups/new")
def admin_new():
    uid = _require_login()
    if uid is None:
        return redirect("/login")
    if not _is_admin():
        return redirect("/login")

    user = _get_user_info()
    return render_template(
        "strategy/admin_edit.html",
        group=None,
        user=user,
        is_admin=user["is_admin"],
    )


@bp.route("/strategy/admin/groups/<int:group_id>/edit")
def admin_edit(group_id):
    uid = _require_login()
    if uid is None:
        return redirect("/login")
    if not _is_admin():
        return redirect("/login")

    group = db.get_strategy_group(group_id)
    if not group:
        return render_template("strategy/404.html", message="策略组不存在"), 404

    user = _get_user_info()
    return render_template(
        "strategy/admin_edit.html",
        group=group,
        user=user,
        is_admin=user["is_admin"],
    )
