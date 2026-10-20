"""截止时间与提醒业务逻辑（组员 C 负责）。

本模块只处理普通 Python 字典、列表和时间：
- 不导入 PyQt6，不发送系统通知，不读写文件。
- 是否弹出通知由界面层决定，本模块只返回“现在应该提醒什么”。

统一任务字典示例（与 task_manager.py 完全一致）：
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

提醒规则（必须统一）：
1. 每个有截止时间的未完成任务最多两个提醒时刻：
   - 自定义提醒：截止时间减去 reminder_minutes_before（默认 60 分钟）；
   - 固定兜底提醒：截止时间前 30 分钟。
2. 两个时刻相同（例如自定义也是 30 分钟）时只算一个提醒。
3. 提醒标识格式为 "截止时间|提前分钟数"，例如
   "2026-10-19T23:59:00|60"、"2026-10-19T23:59:00|30"。
4. 已完成、无截止时间、全局提醒关闭时不提醒。
5. 截止之后不再补发普通提醒；唯一例外是自定义提前 0 分钟，
   截止后 60 秒内的调度容差仍允许提交。
6. 程序重启后可补发“已到提醒时刻但尚未截止”的提醒，
   但要求任务在提醒时刻之前已经存在（比较 reminder_configured_at）。
7. reminder_sent_keys 记录“已提交通知”或“明确跳过”的提醒键；
   切换任务集或关闭全局提醒时，把期间已经错过的键记为跳过并保存，
   重新启用后不补发。

维护说明：
- 组员 C 只需在每个函数里按注释提示实现，函数名、参数和 docstring 不要改。
- 不要导入 PyQt6，不要读写文件，不要发送系统通知。

开发约定：
- 时间统一使用 config.DUE_DATE_FORMAT（YYYY-MM-DDTHH:mm:00）。
- 不需要写测试框架；docstring 里的“典型用例”用于手工验证。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import config


def validate_due_date(due_date) -> bool:
    """判断截止时间是否合法。

    功能：
        校验界面传入的截止时间字符串。

    参数：
        due_date: None 或 "YYYY-MM-DDTHH:mm:00" 字符串。

    返回：
        合法返回 True，非法返回 False。

    规则与边界：
        - None 表示不设置截止时间，视为合法。
        - 必须能按 config.DUE_DATE_FORMAT 完整解析。
        - 本函数只返回真假，不抛异常，由界面决定如何提示。

    是否修改传入数据：
        不会。

    典型用例：
        - validate_due_date(None)：返回 True。
        - validate_due_date("2026-10-19T23:59:00")：返回 True。
        - validate_due_date("2026-02-30T10:00:00")：返回 False。
        - validate_due_date("10-19 23:59")：返回 False。
    """
    if due_date is None:
        return True
    if not isinstance(due_date, str):
        return False
    try:
        datetime.strptime(due_date, config.DUE_DATE_FORMAT)
    except ValueError:
        return False
    return True


def get_due_level(task, now=None) -> str:
    """返回任务卡片边框的紧迫级别。

    功能：
        根据剩余时间判断卡片边框颜色级别。

    参数：
        task: 任务字典。
        now: 当前时间；None 表示使用系统当前本地时间。

    返回：
        "red" / "yellow" / "white" / "gray"

    规则与边界：
        - 已完成或没有截止时间：返回 "gray"。
        - 已逾期或剩余 ≤ 24 小时：返回 "red"。
        - 剩余 > 24 小时且 ≤ 7 天：返回 "yellow"。
        - 剩余 > 7 天：返回 "white"。
        - 按秒精确比较，不受优先级影响。

    是否修改传入数据：
        不会。

    典型用例：
        - 已完成任务：返回 "gray"。
        - 还剩 2 小时：返回 "red"。
        - 还剩 3 天：返回 "yellow"。
        - 还剩 10 天：返回 "white"。
    """
    due_date = task.get("due_date")
    if task.get("status") == config.STATUS_COMPLETED or not due_date:
        return "gray"
    try:
        due = datetime.strptime(due_date, config.DUE_DATE_FORMAT)
    except (TypeError, ValueError):
        return "gray"
    if now is None:
        now = datetime.now()
    remaining = (due - now).total_seconds()
    if remaining <= 24 * 3600:  # 已逾期或剩余不超过 24 小时
        return "red"
    if remaining <= 7 * 24 * 3600:
        return "yellow"
    return "white"


def format_remaining_time(due_date, now=None) -> str:
    """把剩余时间格式化为中文文本。

    功能：
        生成主界面和提醒弹窗显示的剩余时间。

    参数：
        due_date: "YYYY-MM-DDTHH:mm:00" 或 None。
        now: 当前时间；None 表示使用系统当前本地时间。

    返回：
        中文剩余时间字符串。

    规则与边界：
        - 满一日："2日3时15分"。
        - 不足一日："3时15分"。
        - 不足一时："15分"。
        - 不足一分钟且未逾期："不足1分"。
        - 已逾期："已逾期2日3时15分"，为零的单位可省略。
        - due_date 为 None："未设置"。

    是否修改传入数据：
        不会。

    典型用例：
        - 还剩 2 天 3 小时 15 分：返回 "2日3时15分"。
        - 还剩 3 小时 15 分：返回 "3时15分"。
        - 还剩 15 分：返回 "15分"。
        - 已超过截止 2 小时 15 分：返回 "已逾期2时15分"。
        - due_date 为 None：返回 "未设置"。
    """
    if due_date is None:
        return "未设置"
    try:
        due = datetime.strptime(due_date, config.DUE_DATE_FORMAT)
    except (TypeError, ValueError):
        return "未设置"
    if now is None:
        now = datetime.now()
    seconds = int((due - now).total_seconds())
    overdue = seconds < 0
    seconds = abs(seconds)
    if seconds < 60:
        return "已逾期不足1分" if overdue else "不足1分"
    total_minutes = seconds // 60
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}日")
    if hours:
        parts.append(f"{hours}时")
    if minutes:
        parts.append(f"{minutes}分")
    text = "".join(parts) or "不足1分"
    return f"已逾期{text}" if overdue else text


def _parse_due(task) -> datetime | None:
    """解析任务截止时间；无截止时间或格式非法返回 None。"""
    due_date = task.get("due_date")
    if not due_date:
        return None
    try:
        return datetime.strptime(due_date, config.DUE_DATE_FORMAT)
    except (TypeError, ValueError):
        return None


def _candidate_reminders(task):
    """返回任务的候选提醒（分钟数, 提醒时刻, 提醒键）列表；无效任务返回 []。"""
    if task.get("status") == config.STATUS_COMPLETED:
        return []
    due = _parse_due(task)
    if due is None:
        return []
    minutes = task.get("reminder_minutes_before")
    if minutes is None:
        minutes = config.DEFAULT_REMINDER_MINUTES
    candidates = []
    for m in sorted({int(minutes), config.FALLBACK_REMINDER_MINUTES}):
        reminder_time = due - timedelta(minutes=m)
        key = f"{task['due_date']}|{m}"
        candidates.append((m, reminder_time, key))
    return candidates


def get_pending_reminders(tasks, reminders_enabled=True, now=None) -> list:
    """找出当前应当弹出的提醒。

    功能：
        根据自定义提前量和固定 30 分钟兜底规则，返回待提醒项目。

    参数：
        tasks: 任务字典列表。
        reminders_enabled: 全局提醒开关。
        now: 当前时间；None 表示使用系统当前本地时间。

    返回：
        提醒字典列表，每项至少包含：
        {"task_id": ..., "title": ..., "due_date": ..., "reminder_key": ...}

    规则与边界：
        - reminders_enabled 为 False 时直接返回 []。
        - 跳过已完成、没有截止时间、已经发过相同 reminder_key 的任务。
        - 自定义提前量为 30 时，与固定 30 分钟合并，只产生一个提醒键。
        - 普通提醒必须“已到提醒时刻且尚未截止”才返回；
          截止之后不补发。
        - 例外：自定义提前 0 分钟时，截止后 60 秒内仍允许返回一次。
        - 重启补发时，要求 reminder_configured_at 不晚于提醒时刻。
        - 本函数不修改任务，也不发送通知。

    是否修改传入数据：
        不会。

    典型用例：
        - 提前 60 分钟的任务，在截止前 60 分钟和 30 分钟各返回一次。
        - 提前 30 分钟的任务，只在截止前 30 分钟返回一次。
        - 提前 5 分钟的任务，先在 30 分钟返回，再在 5 分钟返回。
        - 已完成任务：不返回。
        - reminders_enabled=False：返回 []。
    """
    if not reminders_enabled:
        return []
    if now is None:
        now = datetime.now()
    result = []
    for task in tasks:
        configured = task.get("reminder_configured_at") or ""
        due = _parse_due(task)
        for _m, reminder_time, key in _candidate_reminders(task):
            if key in task.get("reminder_sent_keys", []):
                continue
            # 任务在提醒时刻之后才配置提醒，不追补该时刻
            if configured > reminder_time.strftime(config.DUE_DATE_FORMAT):
                continue
            if _m == 0:
                # 到期提醒：允许截止后 60 秒内的调度容差
                if not (reminder_time <= now <= due + timedelta(seconds=60)):
                    continue
            else:
                if not (reminder_time <= now <= due):
                    continue
            result.append(
                {
                    "task_id": task["id"],
                    "title": task["title"],
                    "due_date": task["due_date"],
                    "reminder_key": key,
                }
            )
    return result


def mark_reminder_sent(task, reminder_key: str) -> None:
    """记录某个提醒已经发出。

    功能：
        把 reminder_key 写入任务的 reminder_sent_keys，
        表示该提醒已经提交或已被明确跳过，避免再次提醒。

    参数：
        task: 任务字典。
        reminder_key: "截止时间|提前分钟数" 格式的提醒标识。

    返回：
        无返回值。

    规则与边界：
        - reminder_key 已存在时不重复追加。
        - 通知提交成功、或因切换任务集/关闭提醒而主动跳过时都调用本函数。
        - 只修改 reminder_sent_keys，不改变 updated_at。
        - 本函数不保存文件，保存由界面调用存储模块完成。

    是否修改传入数据：
        会，直接修改 task["reminder_sent_keys"]。

    典型用例：
        - mark_reminder_sent(task, "2026-10-19T23:59:00|60")：列表新增该键。
        - 再次传入同一个键：列表不重复添加。
    """
    keys = task.setdefault("reminder_sent_keys", [])
    if reminder_key not in keys:
        keys.append(reminder_key)


def next_reminder_time(tasks, reminders_enabled=True, now=None) -> datetime | None:
    """返回下一个尚未处理的未来提醒时刻；没有则返回 None。

    用于界面层安排较精确的一次性 QTimer；规则与 get_pending_reminders 一致。
    """
    if not reminders_enabled:
        return None
    if now is None:
        now = datetime.now()
    candidates = []
    for task in tasks:
        configured = task.get("reminder_configured_at") or ""
        for _m, reminder_time, key in _candidate_reminders(task):
            if key in task.get("reminder_sent_keys", []):
                continue
            if configured > reminder_time.strftime(config.DUE_DATE_FORMAT):
                continue
            if reminder_time > now:
                candidates.append(reminder_time)
    return min(candidates) if candidates else None


def mark_missed_reminders_as_skipped(tasks, now=None) -> bool:
    """把“已到提醒时刻但尚未处理”的键记为跳过，返回是否有变化。

    用于切换任务集或切换全局提醒开关：期间错过的提醒不追补，
    仅允许未来新触发的时刻。只修改 reminder_sent_keys，不更新 updated_at。
    """
    if now is None:
        now = datetime.now()
    marked = False
    for task in tasks:
        configured = task.get("reminder_configured_at") or ""
        for _m, reminder_time, key in _candidate_reminders(task):
            if key in task.get("reminder_sent_keys", []):
                continue
            if configured > reminder_time.strftime(config.DUE_DATE_FORMAT):
                continue
            if reminder_time <= now:
                mark_reminder_sent(task, key)
                marked = True
    return marked
