"""任务业务逻辑（组员 B 负责）。

本模块只处理普通 Python 字典和列表：
- 不导入 PyQt6，不读写文件，不拼接路径。
- 不发送系统通知，不处理提醒时间。

统一任务字典示例（每个任务都必须包含全部字段）：
{
    "id": "31594232-239b-4d40-9319-65f4527796f3",
    "title": "完成 Python 作业",
    "description": "提交代码与报告",
    "priority": "高",
    "status": "未完成",
    "due_date": "2026-10-19T23:59:00",
    "reminder_minutes_before": 60,
    "reminder_configured_at": "2026-10-18T15:20:00",
    "reminder_sent_keys": [],
    "created_at": "2026-10-18T15:20:00",
    "updated_at": "2026-10-18T15:20:00",
    "completed_at": None,
}

维护说明：
- 组员 B 只需在每个函数里按注释提示实现，函数名、参数和 docstring 不要改。
- 不要导入 PyQt6，不要读写文件，不要写相对路径。

开发约定：
1. 时间字符串统一使用 config.DUE_DATE_FORMAT（YYYY-MM-DDTHH:mm:00）。
2. 优先级只能取 config.PRIORITIES，状态只能取 config.STATUSES。
3. 只有明确标注“会修改传入数据”的函数才能修改列表或字典。
4. 不需要写测试框架；docstring 里的“典型用例”用于手工验证。
"""

from __future__ import annotations

import uuid
from datetime import datetime

import config


def _now_text() -> str:
    """返回当前本地时间字符串，供组员 B 直接使用。"""
    return datetime.now().strftime(config.DUE_DATE_FORMAT)


def _normalize_title(title) -> str:
    """去掉首尾空白；为空或不是字符串时抛 ValueError。"""
    if not isinstance(title, str):
        raise ValueError("任务标题必须是字符串")
    title = title.strip()
    if not title:
        raise ValueError("任务标题不能为空")
    return title


def _is_valid_due_date(due_date) -> bool:
    """校验截止时间字符串（阶段 1 本地实现，与 reminder_manager.validate_due_date 规则一致）。"""
    if due_date is None:
        return True
    if not isinstance(due_date, str):
        return False
    try:
        datetime.strptime(due_date, config.DUE_DATE_FORMAT)
    except ValueError:
        return False
    return True


def _validate_priority(priority) -> None:
    if priority not in config.PRIORITIES:
        raise ValueError(f"优先级必须是 {list(config.PRIORITIES)} 之一")


def _validate_reminder_minutes(minutes) -> None:
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise ValueError("提醒提前分钟数必须是整数")
    if not (config.REMINDER_MINUTES_MIN <= minutes <= config.REMINDER_MINUTES_MAX):
        raise ValueError(
            f"提醒提前分钟数必须在 {config.REMINDER_MINUTES_MIN}–{config.REMINDER_MINUTES_MAX} 之间"
        )


_PRIORITY_ORDER = {
    config.PRIORITY_HIGH: 0,
    config.PRIORITY_MEDIUM: 1,
    config.PRIORITY_LOW: 2,
}


def add_task(tasks, title, priority="中", description="", due_date=None,
             reminder_minutes_before=60) -> dict:
    """新建任务并追加到任务列表。

    功能：
        生成 UUID 和创建时间，补齐任务字典的全部字段，再追加到 tasks。

    参数：
        tasks: 任务字典列表。
        title: 标题；去掉首尾空白后不能为空。
        priority: "高" / "中" / "低"，默认 "中"。
        description: 备注，可为空字符串。
        due_date: "YYYY-MM-DDTHH:mm:00" 或 None。
        reminder_minutes_before: 0–10080 的整数，默认 60。

    返回：
        新任务字典（包含 config.TASK_FIELDS 的全部字段）。

    规则与边界：
        - 标题为空、优先级非法、日期非法、提醒分钟数越界时抛 ValueError。
        - 新任务 status 必须是 "未完成"。
        - 新任务 completed_at 必须是 None（JSON 中为 null）。
        - reminder_sent_keys 初始为空列表。
        - reminder_configured_at 与 created_at 使用当前时间。

    是否修改传入数据：
        会，向 tasks 列表追加一个新任务。

    典型用例：
        - add_task([], "  写作业  ", priority="高")：返回的任务 title 为 "写作业"。
        - add_task([], "")：抛出 ValueError。
        - add_task([], "复习", due_date=None)：任务没有截止时间。
    """
    title = _normalize_title(title)
    _validate_priority(priority)
    if not _is_valid_due_date(due_date):
        raise ValueError(f"截止时间必须是 None 或 {config.DUE_DATE_FORMAT} 格式的字符串")
    _validate_reminder_minutes(reminder_minutes_before)
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise ValueError("备注必须是字符串")
    now = _now_text()
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "priority": priority,
        "status": config.STATUS_PENDING,
        "due_date": due_date,
        "reminder_minutes_before": reminder_minutes_before,
        "reminder_configured_at": now,
        "reminder_sent_keys": [],
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    tasks.append(task)
    return task


def update_task(tasks, task_id, changes: dict) -> dict | None:
    """按任务 ID 修改任务字段。

    功能：
        只修改 changes 中出现的字段，其他字段保持原值。

    参数：
        tasks: 任务字典列表。
        task_id: 要修改的任务 UUID。
        changes: 待修改字段的字典；允许 title、description、priority、
            due_date、reminder_minutes_before。

    返回：
        修改成功返回任务字典；找不到 task_id 时返回 None。

    规则与边界：
        - 不允许修改 id、created_at、status、completed_at。
        - changes 中没有 due_date 键表示不改截止时间；
          传 due_date=None 表示清除截止时间。
        - 修改截止时间或提醒提前量时，清空 reminder_sent_keys，
          并把 reminder_configured_at 更新为当前时间。
        - 任务内容实际变化时更新 updated_at。
        - 标题为空、优先级非法、日期非法、提醒分钟数越界时抛 ValueError。

    是否修改传入数据：
        会，直接修改 tasks 中对应的任务字典。

    典型用例：
        - update_task(tasks, task_id, {"title": "新标题"})：返回的任务标题已更新。
        - update_task(tasks, task_id, {"due_date": None})：截止时间被清除。
        - update_task(tasks, "不存在的 ID", {"title": "x"})：返回 None，列表不变。
    """
    task = next((t for t in tasks if t.get("id") == task_id), None)
    if task is None:
        return None

    allowed_keys = ("title", "description", "priority", "due_date", "reminder_minutes_before")
    for key in changes:
        if key not in allowed_keys:
            raise ValueError(f"不允许修改字段：{key}")

    # 先校验，全部合法才应用
    if "title" in changes:
        changes = dict(changes)
        changes["title"] = _normalize_title(changes["title"])
    if "priority" in changes:
        _validate_priority(changes["priority"])
    if "due_date" in changes and not _is_valid_due_date(changes["due_date"]):
        raise ValueError(f"截止时间必须是 None 或 {config.DUE_DATE_FORMAT} 格式的字符串")
    if "reminder_minutes_before" in changes:
        _validate_reminder_minutes(changes["reminder_minutes_before"])
    if "description" in changes:
        if changes["description"] is None:
            changes = dict(changes)
            changes["description"] = ""
        elif not isinstance(changes["description"], str):
            raise ValueError("备注必须是字符串")

    changed = any(task.get(key) != value for key, value in changes.items())
    if not changed:
        return task

    for key, value in changes.items():
        task[key] = value

    # 修改截止时间或提醒提前量时，旧提醒记录作废，重新按新安排判断
    if "due_date" in changes or "reminder_minutes_before" in changes:
        task["reminder_sent_keys"] = []
        task["reminder_configured_at"] = _now_text()

    task["updated_at"] = _now_text()
    return task


def delete_task(tasks, task_id) -> bool:
    """按任务 ID 删除任务。

    功能：
        从 tasks 中移除指定任务。

    参数：
        tasks: 任务字典列表。
        task_id: 要删除的任务 UUID。

    返回：
        删除成功返回 True；找不到 task_id 返回 False。

    规则与边界：
        - 只删除一个匹配任务，不按标题或列表位置删除。
        - 删除确认由界面负责，本函数不弹窗。

    是否修改传入数据：
        会，从 tasks 列表中移除任务。

    典型用例：
        - delete_task(tasks, task_id)：任务存在时返回 True，列表长度减 1。
        - delete_task(tasks, "不存在的 ID")：返回 False，列表不变。
    """
    for index, task in enumerate(tasks):
        if task.get("id") == task_id:
            del tasks[index]
            return True
    return False


def set_task_completed(tasks, task_id, completed=True) -> bool:
    """设置任务为已完成或撤销完成。

    功能：
        切换任务状态，并维护 completed_at 与 updated_at。

    参数：
        tasks: 任务字典列表。
        task_id: 任务 UUID。
        completed: True 表示标记完成，False 表示撤销完成。

    返回：
        找到任务并成功处理返回 True；找不到 task_id 返回 False。

    规则与边界：
        - 完成时写入当前时间到 completed_at。
        - 撤销完成时把 completed_at 置为 None。
        - 撤销完成时同时把 reminder_configured_at 更新为当前时间，
          但保留原有 reminder_sent_keys：已发过的提醒不重发，
          撤销前已经过去、尚未处理的提醒也不追补。
        - 完成时不要修改 reminder_configured_at 或 reminder_sent_keys。
        - 重复设置相同状态不刷新完成时间。
        - 状态变化时更新 updated_at。

    是否修改传入数据：
        会，直接修改 tasks 中对应的任务字典。

    典型用例：
        - set_task_completed(tasks, task_id, True)：completed_at 变为当前时间。
        - 再调用一次 set_task_completed(tasks, task_id, True)：completed_at 不变。
        - set_task_completed(tasks, task_id, False)：completed_at 变为 None，
          reminder_sent_keys 保留，reminder_configured_at 更新为撤销时间。
    """
    task = next((t for t in tasks if t.get("id") == task_id), None)
    if task is None:
        return False
    if completed:
        if task.get("status") == config.STATUS_COMPLETED:
            return True
        task["status"] = config.STATUS_COMPLETED
        task["completed_at"] = _now_text()
    else:
        if task.get("status") != config.STATUS_COMPLETED:
            return True
        task["status"] = config.STATUS_PENDING
        task["completed_at"] = None
        # 保留已发送的提醒键，只更新配置时刻：撤销前错过的提醒不追补
        task["reminder_configured_at"] = _now_text()
    task["updated_at"] = _now_text()
    return True


def get_view_tasks(tasks, view="due_date") -> list:
    """按视图返回排好序的任务列表。

    功能：
        生成三个视图对应的展示列表，不改变原始任务列表。

    参数：
        tasks: 任务字典列表。
        view: 只能是 "due_date"、"priority"、"completed"。

    返回：
        新的任务列表。

    规则与边界：
        - due_date：只包含未完成任务；按截止时间升序，逾期任务仍按原时间
          靠前，没有截止时间的排最后；时间相同时优先级高的在前。
        - priority：只包含未完成任务；按高 → 中 → 低；同级按截止时间
          升序，没有截止时间的排最后。
        - completed：只包含已完成任务；按 completed_at 从新到旧，
          没有完成时间的排最后。
        - 仍未分出的顺序按 created_at 从早到晚，最后按 id。
        - view 非法时抛 ValueError。

    是否修改传入数据：
        不会，返回新列表，原始 tasks 和任务字典都不改变。

    典型用例：
        - get_view_tasks(tasks, "due_date")：结果中不含已完成任务。
        - get_view_tasks(tasks, "priority")：第一个任务是高优先级。
        - get_view_tasks(tasks, "completed")：最新完成的任务在最前面。
    """
    if view not in config.VIEW_MODES:
        raise ValueError(f"view 只能是 {list(config.VIEW_MODES)} 之一")

    def base_key(task):
        return (task.get("created_at") or "", task.get("id") or "")

    if view == config.VIEW_DUE_DATE:
        subset = [t for t in tasks if t.get("status") != config.STATUS_COMPLETED]
        subset.sort(key=lambda t: (
            t.get("due_date") is None,
            t.get("due_date") or "",
            _PRIORITY_ORDER.get(t.get("priority"), 9),
            *base_key(t),
        ))
        return subset

    if view == config.VIEW_PRIORITY:
        subset = [t for t in tasks if t.get("status") != config.STATUS_COMPLETED]
        subset.sort(key=lambda t: (
            _PRIORITY_ORDER.get(t.get("priority"), 9),
            t.get("due_date") is None,
            t.get("due_date") or "",
            *base_key(t),
        ))
        return subset

    # completed 视图：先按 created_at、id 稳定排序，再按完成时间倒序（None 排最后）
    subset = [t for t in tasks if t.get("status") == config.STATUS_COMPLETED]
    subset.sort(key=base_key)
    subset.sort(key=lambda t: t.get("completed_at") or "", reverse=True)
    return subset


def get_task_statistics(tasks) -> dict:
    """统计任务总数、未完成数、已完成数和完成率。

    功能：
        为界面顶部或设置页提供统计数字。

    参数：
        tasks: 任务字典列表。

    返回：
        {"total": 整数, "pending": 整数, "completed": 整数,
         "completion_rate": 0 到 100 的数值}

    规则与边界：
        - 没有任务时 total、pending、completed 均为 0，
          completion_rate 必须为 0。
        - completion_rate = completed / total * 100。

    是否修改传入数据：
        不会。

    典型用例：
        - 空列表：{"total": 0, "pending": 0, "completed": 0, "completion_rate": 0}。
        - 2 个任务完成 1 个：完成率为 50。
    """
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == config.STATUS_COMPLETED)
    pending = total - completed
    completion_rate = 0 if total == 0 else completed / total * 100
    return {
        "total": total,
        "pending": pending,
        "completed": completed,
        "completion_rate": completion_rate,
    }
