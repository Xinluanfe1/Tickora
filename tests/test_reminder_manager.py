"""reminder_manager 的提醒规则测试（纯函数，固定 now，不写磁盘）。"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

_TMP_ENV = tempfile.mkdtemp(prefix="todolist_reminder_env_")
os.environ["LOCALAPPDATA"] = _TMP_ENV

import config
import reminder_manager
import task_manager

NOW = datetime(2026, 10, 19, 12, 0, 0)
DUE = "2026-10-19T15:00:00"


def make_task(due=DUE, minutes=60, configured="2026-10-19T10:00:00", status=None):
    tasks = []
    task = task_manager.add_task(
        tasks, "任务", due_date=due, reminder_minutes_before=minutes
    )
    if configured is not None:
        task["reminder_configured_at"] = configured
    if status is not None:
        task["status"] = status
    return tasks[0]


class ValidateDueDateTest(unittest.TestCase):
    def test_valid_inputs(self):
        self.assertTrue(reminder_manager.validate_due_date(None))
        self.assertTrue(reminder_manager.validate_due_date("2026-10-19T23:59:00"))

    def test_invalid_inputs(self):
        self.assertFalse(reminder_manager.validate_due_date("2026-02-30T10:00:00"))
        self.assertFalse(reminder_manager.validate_due_date("10-19 23:59"))
        self.assertFalse(reminder_manager.validate_due_date(123))


class DueLevelTest(unittest.TestCase):
    def test_gray_for_completed_or_no_due(self):
        self.assertEqual(
            reminder_manager.get_due_level(make_task(status=config.STATUS_COMPLETED), NOW),
            "gray",
        )
        self.assertEqual(reminder_manager.get_due_level(make_task(due=None), NOW), "gray")

    def test_level_boundaries(self):
        # 剩余 2 小时：red
        self.assertEqual(
            reminder_manager.get_due_level(make_task(due="2026-10-19T14:00:00"), NOW), "red"
        )
        # 已逾期：red
        self.assertEqual(
            reminder_manager.get_due_level(make_task(due="2026-10-19T11:00:00"), NOW), "red"
        )
        # 剩余 3 天：yellow
        self.assertEqual(
            reminder_manager.get_due_level(make_task(due="2026-10-22T12:00:00"), NOW),
            "yellow",
        )
        # 剩余 10 天：white
        self.assertEqual(
            reminder_manager.get_due_level(make_task(due="2026-10-29T12:00:00"), NOW),
            "white",
        )


class FormatRemainingTimeTest(unittest.TestCase):
    def test_not_set(self):
        self.assertEqual(reminder_manager.format_remaining_time(None, NOW), "未设置")

    def test_chinese_formats(self):
        due = (NOW + timedelta(days=2, hours=3, minutes=15)).strftime(config.DUE_DATE_FORMAT)
        self.assertEqual(reminder_manager.format_remaining_time(due, NOW), "2日3时15分")
        due = (NOW + timedelta(hours=3, minutes=15)).strftime(config.DUE_DATE_FORMAT)
        self.assertEqual(reminder_manager.format_remaining_time(due, NOW), "3时15分")
        due = (NOW + timedelta(minutes=15)).strftime(config.DUE_DATE_FORMAT)
        self.assertEqual(reminder_manager.format_remaining_time(due, NOW), "15分")
        due = (NOW + timedelta(seconds=30)).strftime(config.DUE_DATE_FORMAT)
        self.assertEqual(reminder_manager.format_remaining_time(due, NOW), "不足1分")

    def test_overdue_formats(self):
        due = (NOW - timedelta(hours=2, minutes=15)).strftime(config.DUE_DATE_FORMAT)
        self.assertEqual(reminder_manager.format_remaining_time(due, NOW), "已逾期2时15分")
        due = NOW.strftime(config.DUE_DATE_FORMAT)
        self.assertEqual(
            reminder_manager.format_remaining_time(due, NOW + timedelta(seconds=30)),
            "已逾期不足1分",
        )


class PendingRemindersTest(unittest.TestCase):
    def _keys(self, tasks, now, enabled=True):
        return [
            item["reminder_key"]
            for item in reminder_manager.get_pending_reminders(
                tasks, reminders_enabled=enabled, now=now
            )
        ]

    def test_custom_60_then_fallback_30(self):
        tasks = [make_task(minutes=60)]
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 14, 0, 0)), [f"{DUE}|60"]
        )
        # 60 分钟提醒已处理，30 分钟时刻再触发
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|60")
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 14, 30, 0)), [f"{DUE}|30"]
        )

    def test_custom_30_merges_into_one(self):
        tasks = [make_task(minutes=30)]
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 14, 30, 0)), [f"{DUE}|30"]
        )

    def test_custom_5_after_fallback(self):
        tasks = [make_task(minutes=5)]
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 14, 30, 0)), [f"{DUE}|30"]
        )
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|30")
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 14, 55, 0)), [f"{DUE}|5"]
        )

    def test_zero_minute_60_second_grace(self):
        tasks = [make_task(minutes=0)]
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|30")
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 15, 0, 30)), [f"{DUE}|0"]
        )
        self.assertEqual(self._keys(tasks, datetime(2026, 10, 19, 15, 1, 1)), [])

    def test_no_catch_up_after_due(self):
        tasks = [make_task(minutes=60)]
        self.assertEqual(self._keys(tasks, datetime(2026, 10, 19, 15, 1, 0)), [])

    def test_skips_completed_no_due_disabled(self):
        tasks = [
            make_task(status=config.STATUS_COMPLETED),
            make_task(due=None),
            make_task(),
        ]
        self.assertEqual(
            self._keys(tasks, datetime(2026, 10, 19, 14, 0, 0), enabled=False), []
        )

    def test_configured_after_reminder_time_is_skipped(self):
        # 任务在 14:10 才配置提醒，14:00 的旧时刻不追补
        tasks = [make_task(minutes=60, configured="2026-10-19T14:10:00")]
        self.assertEqual(self._keys(tasks, datetime(2026, 10, 19, 14, 20, 0)), [])

    def test_sent_key_not_repeated(self):
        tasks = [make_task(minutes=60)]
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|60")
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|60")
        self.assertEqual(tasks[0]["reminder_sent_keys"], [f"{DUE}|60"])
        updated_at = tasks[0]["updated_at"]
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|30")
        self.assertEqual(tasks[0]["updated_at"], updated_at)  # 不更新 updated_at


class NextReminderTimeTest(unittest.TestCase):
    def test_next_future_moment(self):
        tasks = [make_task(minutes=60)]
        self.assertEqual(
            reminder_manager.next_reminder_time(tasks, now=NOW),
            datetime(2026, 10, 19, 14, 0, 0),
        )
        reminder_manager.mark_reminder_sent(tasks[0], f"{DUE}|60")
        self.assertEqual(
            reminder_manager.next_reminder_time(tasks, now=NOW),
            datetime(2026, 10, 19, 14, 30, 0),
        )

    def test_none_when_disabled_or_nothing_left(self):
        self.assertIsNone(reminder_manager.next_reminder_time([], now=NOW))
        self.assertIsNone(
            reminder_manager.next_reminder_time([make_task()], reminders_enabled=False, now=NOW)
        )


class MissedSkipTest(unittest.TestCase):
    def test_past_unhandled_keys_marked_skipped(self):
        tasks = [make_task(minutes=60)]
        now = datetime(2026, 10, 19, 15, 30, 0)
        self.assertTrue(reminder_manager.mark_missed_reminders_as_skipped(tasks, now=now))
        self.assertEqual(
            tasks[0]["reminder_sent_keys"], [f"{DUE}|30", f"{DUE}|60"]
        )
        self.assertFalse(reminder_manager.mark_missed_reminders_as_skipped(tasks, now=now))

    def test_future_keys_not_marked(self):
        tasks = [make_task(minutes=60)]
        self.assertFalse(
            reminder_manager.mark_missed_reminders_as_skipped(tasks, now=NOW)
        )
        self.assertEqual(tasks[0]["reminder_sent_keys"], [])


if __name__ == "__main__":
    unittest.main()
