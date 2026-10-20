"""任务新增/编辑对话框：阶段 1 已接入真实交互。"""

from __future__ import annotations

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

import config
import task_manager
from ui.style import DIALOG_QSS

# Qt 的日期格式与 Python strftime 不同，必须单独使用 Qt 格式（T 用引号转义为字面量）
_QT_DUE_FORMAT = "yyyy-MM-dd'T'HH:mm:00"


class TaskDialog(QDialog):
    """新增（task 为 None）或编辑（task 为字典）任务。

    校验由 task_manager 完成：非法输入弹出提示，对话框不关闭。
    编辑模式下提供“删除任务”，带二次确认。
    """

    def __init__(self, tasks: list, task: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self._tasks = tasks
        self._task = task
        self._deleted = False
        self._result_task: dict | None = None

        self.setWindowTitle("编辑任务" if task else "新建任务")
        self.resize(480, 360)
        self.setStyleSheet(DIALOG_QSS)

        form = QFormLayout()

        self.title_edit = QLineEdit()
        form.addRow("标题（必填）：", self.title_edit)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(config.PRIORITIES)
        self.priority_combo.setCurrentText(config.DEFAULT_PRIORITY)
        form.addRow("优先级：", self.priority_combo)

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("备注（可选）")
        self.desc_edit.setFixedHeight(72)
        form.addRow("备注：", self.desc_edit)

        self.has_due_check = QCheckBox("设置截止时间")
        form.addRow("", self.has_due_check)

        self.due_edit = QDateTimeEdit()
        self.due_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        form.addRow("截止时间：", self.due_edit)

        self.remind_spin = QSpinBox()
        self.remind_spin.setRange(config.REMINDER_MINUTES_MIN, config.REMINDER_MINUTES_MAX)
        self.remind_spin.setValue(config.DEFAULT_REMINDER_MINUTES)
        self.remind_spin.setSuffix(" 分钟")
        form.addRow("提前提醒：", self.remind_spin)

        self.has_due_check.toggled.connect(self.due_edit.setEnabled)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self.button_box)

        if self._task is not None:
            self._populate()
            delete_btn = self.button_box.addButton("删除任务", QDialogButtonBox.ButtonRole.DestructiveRole)
            delete_btn.clicked.connect(self._on_delete)

    def _populate(self) -> None:
        task = self._task
        self.title_edit.setText(task.get("title", ""))
        self.priority_combo.setCurrentText(task.get("priority", config.DEFAULT_PRIORITY))
        self.desc_edit.setPlainText(task.get("description", ""))
        due = task.get("due_date")
        if due:
            dt = QDateTime.fromString(due, _QT_DUE_FORMAT)
            if dt.isValid():
                self.due_edit.setDateTime(dt)
            self.has_due_check.setChecked(True)
        else:
            self.has_due_check.setChecked(False)
        self.remind_spin.setValue(task.get("reminder_minutes_before", config.DEFAULT_REMINDER_MINUTES))

    def _on_save(self) -> None:
        title = self.title_edit.text()
        priority = self.priority_combo.currentText()
        description = self.desc_edit.toPlainText()
        if self.has_due_check.isChecked():
            due = self.due_edit.dateTime().toString(_QT_DUE_FORMAT)
        else:
            due = None
        remind = self.remind_spin.value()

        try:
            if self._task is None:
                self._result_task = task_manager.add_task(
                    self._tasks,
                    title,
                    priority=priority,
                    description=description,
                    due_date=due,
                    reminder_minutes_before=remind,
                )
            else:
                self._result_task = task_manager.update_task(
                    self._tasks,
                    self._task["id"],
                    {
                        "title": title,
                        "priority": priority,
                        "description": description,
                        "due_date": due,
                        "reminder_minutes_before": remind,
                    },
                )
        except ValueError as exc:
            QMessageBox.warning(self, "无法保存任务", str(exc))
            return
        super().accept()

    def _on_delete(self) -> None:
        answer = QMessageBox.question(
            self,
            "删除任务",
            f"确定删除任务“{self._task.get('title', '')}”吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            task_manager.delete_task(self._tasks, self._task["id"])
            self._deleted = True
            super().accept()

    def was_deleted(self) -> bool:
        return self._deleted

    def result_task(self) -> dict | None:
        return self._result_task
