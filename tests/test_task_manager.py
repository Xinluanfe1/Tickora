"""task_manager 的纯逻辑测试（不写磁盘）。"""

import os
import tempfile
import unittest

# 导入任何项目模块前，先把 LOCALAPPDATA 指向临时目录，
# 避免测试进程意外读写真实用户数据。
_TMP_ENV = tempfile.mkdtemp(prefix="todolist_task_tests_env_")
os.environ["LOCALAPPDATA"] = _TMP_ENV

import config
import task_manager


class AddTaskTest(unittest.TestCase):
    def test_empty_title_raises(self):
        for bad in ("", "   ", "\t\n"):
            with self.assertRaises(ValueError):
                task_manager.add_task([], bad)

    def test_new_task_has_all_fields(self):
        tasks = []
        task = task_manager.add_task(tasks, "  写作业  ", priority="高", due_date="2026-10-19T23:59:00")
        self.assertEqual(task["title"], "写作业")
        self.assertEqual(task["status"], config.STATUS_PENDING)
        self.assertIsNone(task["completed_at"])
        self.assertEqual(task["reminder_sent_keys"], [])
        self.assertEqual(task["reminder_minutes_before"], 60)
        self.assertEqual(task["due_date"], "2026-10-19T23:59:00")
        self.assertIn("id", task)
        self.assertEqual(tasks, [task])

    def test_invalid_priority_or_minutes_raises(self):
        with self.assertRaises(ValueError):
            task_manager.add_task([], "任务", priority="紧急")
        with self.assertRaises(ValueError):
            task_manager.add_task([], "任务", reminder_minutes_before=-1)
        with self.assertRaises(ValueError):
            task_manager.add_task([], "任务", reminder_minutes_before=10081)
        with self.assertRaises(ValueError):
            task_manager.add_task([], "任务", due_date="2026-02-30T10:00:00")


class CompletionTest(unittest.TestCase):
    def test_completion_lifecycle(self):
        tasks = []
        task = task_manager.add_task(tasks, "复习")
        self.assertIsNone(task["completed_at"])

        self.assertTrue(task_manager.set_task_completed(tasks, task["id"], True))
        first = task["completed_at"]
        self.assertIsNotNone(first)
        self.assertEqual(task["status"], config.STATUS_COMPLETED)
        first_updated = task["updated_at"]

        # 重复设置相同状态：时间不刷新
        self.assertTrue(task_manager.set_task_completed(tasks, task["id"], True))
        self.assertEqual(task["completed_at"], first)
        self.assertEqual(task["updated_at"], first_updated)

        # 撤销完成：completed_at 置空、提醒键保留、reminder_configured_at 更新
        task["reminder_sent_keys"] = ["2026-10-19T23:59:00|60"]
        old_configured = task["reminder_configured_at"]
        self.assertTrue(task_manager.set_task_completed(tasks, task["id"], False))
        self.assertIsNone(task["completed_at"])
        self.assertEqual(task["status"], config.STATUS_PENDING)
        self.assertEqual(task["reminder_sent_keys"], ["2026-10-19T23:59:00|60"])
        self.assertGreaterEqual(task["reminder_configured_at"], old_configured)

    def test_unknown_id(self):
        tasks = []
        self.assertFalse(task_manager.set_task_completed(tasks, "missing", True))
        self.assertFalse(task_manager.delete_task(tasks, "missing"))
        self.assertIsNone(task_manager.update_task(tasks, "missing", {"title": "x"}))


class UpdateTaskTest(unittest.TestCase):
    def test_due_change_clears_reminder_keys(self):
        tasks = []
        task = task_manager.add_task(tasks, "任务", due_date="2026-10-20T10:00:00")
        task["reminder_sent_keys"] = ["2026-10-20T10:00:00|60"]
        old_updated = task["updated_at"]
        updated = task_manager.update_task(tasks, task["id"], {"due_date": "2026-10-21T10:00:00"})
        self.assertEqual(updated["reminder_sent_keys"], [])
        self.assertGreaterEqual(updated["reminder_configured_at"], old_updated)
        self.assertGreaterEqual(updated["updated_at"], old_updated)

    def test_title_only_change_keeps_reminder_keys(self):
        tasks = []
        task = task_manager.add_task(tasks, "任务", due_date="2026-10-20T10:00:00")
        keys = ["2026-10-20T10:00:00|60"]
        task["reminder_sent_keys"] = keys
        updated = task_manager.update_task(tasks, task["id"], {"title": "新标题"})
        self.assertEqual(updated["reminder_sent_keys"], keys)

    def test_clear_due_date(self):
        tasks = []
        task = task_manager.add_task(tasks, "任务", due_date="2026-10-20T10:00:00")
        updated = task_manager.update_task(tasks, task["id"], {"due_date": None})
        self.assertIsNone(updated["due_date"])

    def test_forbidden_and_unknown_keys_raise(self):
        tasks = []
        task = task_manager.add_task(tasks, "任务")
        for key in ("id", "created_at", "status", "completed_at", "other"):
            with self.assertRaises(ValueError):
                task_manager.update_task(tasks, task["id"], {key: "x"})

    def test_no_actual_change_keeps_updated_at(self):
        tasks = []
        task = task_manager.add_task(tasks, "任务")
        before = task["updated_at"]
        task_manager.update_task(tasks, task["id"], {"title": "任务"})
        self.assertEqual(task["updated_at"], before)


class ViewAndStatisticsTest(unittest.TestCase):
    def setUp(self):
        self.tasks = []
        self.high = task_manager.add_task(
            self.tasks, "高优先级", priority="高", due_date="2026-10-21T10:00:00"
        )
        self.early = task_manager.add_task(
            self.tasks, "先截止", priority="低", due_date="2026-10-20T10:00:00"
        )
        self.no_due = task_manager.add_task(self.tasks, "无截止", priority="中")
        self.done = task_manager.add_task(
            self.tasks, "已完成", priority="中", due_date="2026-10-19T10:00:00"
        )
        self.done["status"] = config.STATUS_COMPLETED
        self.done["completed_at"] = "2026-10-18T12:00:00"

    def test_due_date_view(self):
        view = task_manager.get_view_tasks(self.tasks, "due_date")
        self.assertEqual([t["title"] for t in view], ["先截止", "高优先级", "无截止"])

    def test_due_date_tie_uses_priority(self):
        a = task_manager.add_task(self.tasks, "甲", priority="低", due_date="2026-10-22T08:00:00")
        b = task_manager.add_task(self.tasks, "乙", priority="高", due_date="2026-10-22T08:00:00")
        view = task_manager.get_view_tasks(self.tasks, "due_date")
        titles = [t["title"] for t in view]
        self.assertLess(titles.index("乙"), titles.index("甲"))

    def test_priority_view(self):
        view = task_manager.get_view_tasks(self.tasks, "priority")
        self.assertEqual([t["title"] for t in view], ["高优先级", "无截止", "先截止"])

    def test_completed_view(self):
        newer = task_manager.add_task(self.tasks, "新完成", priority="低")
        newer["status"] = config.STATUS_COMPLETED
        newer["completed_at"] = "2026-10-19T09:00:00"
        view = task_manager.get_view_tasks(self.tasks, "completed")
        self.assertEqual([t["title"] for t in view], ["新完成", "已完成"])

    def test_invalid_view_raises(self):
        with self.assertRaises(ValueError):
            task_manager.get_view_tasks(self.tasks, "search")

    def test_statistics(self):
        self.assertEqual(
            task_manager.get_task_statistics([]),
            {"total": 0, "pending": 0, "completed": 0, "completion_rate": 0},
        )
        stats = task_manager.get_task_statistics(self.tasks)
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["pending"], 3)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["completion_rate"], 25)


if __name__ == "__main__":
    unittest.main()
