"""任务对话框的日期格式回归测试（offscreen，不写真实用户数据）。"""

import os
import tempfile
import unittest

_TMP_ENV = tempfile.mkdtemp(prefix="todolist_dialog_env_")
os.environ["LOCALAPPDATA"] = _TMP_ENV
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import QApplication

import task_manager
from ui.task_dialog import TaskDialog


class TaskDialogDateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_edit_saves_qt_date_in_python_format(self):
        tasks = []
        task = task_manager.add_task(tasks, "test")
        dialog = TaskDialog(tasks, task)
        dialog.has_due_check.setChecked(True)
        dialog.due_edit.setDateTime(QDateTime(2026, 10, 20, 0, 21))
        dialog._on_save()
        self.assertEqual(task["due_date"], "2026-10-20T00:21:00")
        dialog.close()

    def test_edit_populates_existing_due_date(self):
        tasks = []
        task = task_manager.add_task(tasks, "test", due_date="2026-10-20T00:21:00")
        dialog = TaskDialog(tasks, task)
        self.assertTrue(dialog.has_due_check.isChecked())
        self.assertEqual(
            dialog.due_edit.dateTime().toString("yyyy-MM-dd'T'HH:mm:00"),
            "2026-10-20T00:21:00",
        )
        dialog.close()


if __name__ == "__main__":
    unittest.main()
