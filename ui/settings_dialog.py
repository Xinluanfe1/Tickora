"""设置对话框：任务集管理、全局提醒、系统托盘与开机自启开关。"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

import config
import storage
import system_integration
from ui.style import DIALOG_QSS


class SettingsDialog(QDialog):
    """任务集管理（新建/切换/导入/导出）与全局设置。

    关闭对话框后，主窗口通过 selected_taskset_id() 判断是否需要切换；
    全局提醒开关在此保存。
    """

    def __init__(self, settings: dict, current_taskset_id: str, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._selected_taskset_id = current_taskset_id

        self.setWindowTitle("设置")
        self.resize(460, 460)
        self.setStyleSheet(DIALOG_QSS)

        root = QVBoxLayout(self)

        taskset_box = QGroupBox("任务集")
        taskset_layout = QVBoxLayout(taskset_box)
        self.taskset_list = QListWidget()
        taskset_layout.addWidget(self.taskset_list)
        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("新建")
        self.switch_btn = QPushButton("切换到此任务集")
        self.import_btn = QPushButton("导入")
        self.export_btn = QPushButton("导出")
        for btn in (self.new_btn, self.switch_btn, self.import_btn, self.export_btn):
            btn_row.addWidget(btn)
        taskset_layout.addLayout(btn_row)
        self.switch_hint = QLabel()
        self.switch_hint.setStyleSheet("color: #666666;")
        taskset_layout.addWidget(self.switch_hint)
        root.addWidget(taskset_box)

        remind_box = QGroupBox("提醒")
        remind_layout = QVBoxLayout(remind_box)
        self.reminders_check = QCheckBox("启用全局提醒")
        remind_layout.addWidget(self.reminders_check)
        root.addWidget(remind_box)

        integration_box = QGroupBox("系统集成")
        integration_layout = QVBoxLayout(integration_box)
        self.autostart_check = QCheckBox("开机自启（当前用户，默认关闭）")
        self.tray_check = QCheckBox("关闭窗口后驻留系统托盘")
        integration_layout.addWidget(self.autostart_check)
        integration_layout.addWidget(self.tray_check)
        note = QLabel(
            "开机自启写入 HKCU 当前用户注册表（安装版专属项，默认关闭），"
            "仅安装版生效，源码运行环境不支持；Windows 原生通知随全局提醒开关工作。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666;")
        integration_layout.addWidget(note)
        root.addWidget(integration_box)

        about_box = QGroupBox("关于")
        about_layout = QVBoxLayout(about_box)
        logo = QLabel()
        if config.LOGO_FILE.is_file():
            pixmap = QPixmap(str(config.LOGO_FILE))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaledToWidth(
                        180, Qt.TransformationMode.SmoothTransformation
                    )
                )
                logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
                about_layout.addWidget(logo)
        about_layout.addWidget(QLabel(f"版本 {config.APP_VERSION}"))
        about_layout.addWidget(QLabel(f"数据目录：{config.DATA_DIR}"))
        root.addWidget(about_box)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("关闭设置")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

        self.reminders_check.setChecked(bool(self._settings.get("reminders_enabled", True)))
        # 自启状态以本机注册表为准，不信任设置文件中可能过期的记录
        self.autostart_check.setChecked(system_integration.get_autostart_state())
        self.tray_check.setChecked(bool(self._settings.get("close_to_tray", True)))

        self.new_btn.clicked.connect(self._on_create)
        self.switch_btn.clicked.connect(self._on_switch)
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn.clicked.connect(self._on_export)

        self._refresh_taskset_list(select_id=current_taskset_id)

    def _refresh_taskset_list(self, select_id: str | None = None) -> None:
        self.taskset_list.clear()
        tasksets = storage.list_tasksets()
        for summary in tasksets:
            item = QListWidgetItem(summary["name"])
            item.setData(Qt.ItemDataRole.UserRole, summary["id"])
            self.taskset_list.addItem(item)
            if summary["id"] == select_id:
                self.taskset_list.setCurrentItem(item)
        if not tasksets:
            self.switch_hint.setText("尚未创建任何任务集。")
        else:
            self.switch_hint.setText(
                "当前活动任务集已高亮；点击“切换到此任务集”后，关闭设置即生效。"
            )

    def _current_list_id(self) -> str | None:
        item = self.taskset_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_create(self) -> None:
        name, ok = QInputDialog.getText(self, "新建任务集", "任务集名称：")
        if not ok:
            return
        try:
            taskset = storage.create_taskset(name)
        except ValueError as exc:
            QMessageBox.warning(self, "无法创建任务集", str(exc))
            return
        self._refresh_taskset_list(select_id=taskset["taskset_id"])
        self._selected_taskset_id = taskset["taskset_id"]

    def _on_switch(self) -> None:
        taskset_id = self._current_list_id()
        if not taskset_id:
            QMessageBox.information(self, "切换任务集", "请先选择一个任务集。")
            return
        self._selected_taskset_id = taskset_id
        self._refresh_taskset_list(select_id=taskset_id)
        self.switch_hint.setText("已选择切换目标；关闭设置后生效。")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入任务集", "", "任务集 JSON (*.json)"
        )
        if not path:
            return
        display_name = None
        while True:
            try:
                taskset = storage.import_taskset(path, display_name)
                break
            except ValueError as exc:
                if "已存在" in str(exc):
                    new_name, ok = QInputDialog.getText(
                        self, "任务集名称冲突", f"{exc}\n请输入新的显示名称："
                    )
                    if not ok:
                        return
                    display_name = new_name
                else:
                    QMessageBox.warning(self, "导入失败", str(exc))
                    return
            except OSError as exc:
                QMessageBox.warning(self, "导入失败", str(exc))
                return
        self._refresh_taskset_list(select_id=taskset["taskset_id"])

    def _on_export(self) -> None:
        taskset_id = self._current_list_id()
        if not taskset_id:
            QMessageBox.information(self, "导出任务集", "请先选择一个任务集。")
            return
        current_item = self.taskset_list.currentItem()
        suggested = f"{current_item.text()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出任务集", suggested, "任务集 JSON (*.json)"
        )
        if not path:
            return
        try:
            storage.export_taskset(taskset_id, path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def _on_accept(self) -> None:
        self._settings["reminders_enabled"] = self.reminders_check.isChecked()
        self._settings["close_to_tray"] = self.tray_check.isChecked()

        want_autostart = self.autostart_check.isChecked()
        current_autostart = system_integration.get_autostart_state()
        if want_autostart != current_autostart:
            try:
                system_integration.set_autostart(want_autostart, sys.executable)
            except (RuntimeError, OSError) as exc:
                QMessageBox.warning(self, "开机自启设置失败", str(exc))
                self.autostart_check.setChecked(system_integration.get_autostart_state())
        self._settings["autostart_enabled"] = system_integration.get_autostart_state()

        try:
            storage.save_settings(self._settings)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "保存设置失败", str(exc))
            return
        super().accept()

    def selected_taskset_id(self) -> str:
        return self._selected_taskset_id

    def result_settings(self) -> dict:
        return self._settings
