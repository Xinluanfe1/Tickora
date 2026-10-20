"""主窗口：三视图瀑布流、QTimer 提醒调度、QLockFile 单实例与系统托盘。

提醒业务由 reminder_manager 提供规则，通知提交由 system_integration 完成；
本层只负责调度、展示与错误反馈。
"""

from __future__ import annotations

import math
from datetime import datetime

from PyQt6.QtCore import QEvent, QLockFile, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import config
import reminder_manager
import storage
import system_integration
import task_manager
from ui.settings_dialog import SettingsDialog
from ui.style import COLORS, DUE_BORDER_COLORS, PRIORITY_PILL
from ui.task_dialog import TaskDialog

VIEW_LABELS = {
    config.VIEW_DUE_DATE: "按截止时间",
    config.VIEW_PRIORITY: "按优先级",
    config.VIEW_COMPLETED: "已完成",
}

class AlreadyRunningError(RuntimeError):
    """同一用户数据目录已有实例在运行。"""


def _format_display_time(text: str | None) -> str:
    """把内部时间字符串转成 MM-DD HH:mm 展示（阶段 1 的固定格式）。"""
    if not text:
        return ""
    try:
        dt = datetime.strptime(text, config.DUE_DATE_FORMAT)
    except ValueError:
        return text
    return dt.strftime(config.DISPLAY_DUE_FORMAT)


class TaskRow(QFrame):
    """整行任务卡片：完成圆点、标题与时间、优先级标签。"""

    def __init__(
        self,
        task: dict,
        view: str,
        due_level: str,
        remaining_text: str,
        on_open,
        on_toggle_completed,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("taskRow")
        border = DUE_BORDER_COLORS.get(due_level, COLORS["border"])
        self.setStyleSheet(
            f"""
            QFrame#taskRow {{
                background: #FFFFFF;
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QFrame#taskRow:hover {{ background: #FCFCFE; }}
            QLabel {{ border: none; background: transparent; }}
            """
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_open = on_open
        completed = task.get("status") == config.STATUS_COMPLETED

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(12)

        check = QPushButton("✓" if completed else "")
        check.setObjectName("checkBtn")
        check.setFixedSize(22, 22)
        check.setCursor(Qt.CursorShape.PointingHandCursor)
        if completed:
            check.setStyleSheet(
                "QPushButton#checkBtn { background: #007AFF; border: none;"
                " border-radius: 11px; color: white; font-size: 12px; font-weight: 700; }"
            )
        else:
            check.setStyleSheet(
                "QPushButton#checkBtn { background: transparent;"
                " border: 1.5px solid #C7C7CC; border-radius: 11px; }"
                "QPushButton#checkBtn:hover { border-color: #007AFF; }"
            )
        check.clicked.connect(lambda: on_toggle_completed(task))
        layout.addWidget(check, 0, Qt.AlignmentFlag.AlignVCenter)

        middle = QVBoxLayout()
        middle.setSpacing(4)
        title = QLabel(task.get("title", ""))
        title.setWordWrap(True)
        if completed:
            title.setStyleSheet("color: #8E8E93; font-size: 15px;")
            font = title.font()
            font.setStrikeOut(True)
            title.setFont(font)
        else:
            title.setStyleSheet("color: #1D1D1F; font-size: 15px; font-weight: 600;")
        middle.addWidget(title)

        if view == config.VIEW_COMPLETED:
            completed_at = _format_display_time(task.get("completed_at"))
            meta_text = f"完成于 {completed_at}" if completed_at else "完成时间未知"
        else:
            due = task.get("due_date")
            meta_text = (
                f"截止 {_format_display_time(due)} · 剩余 {remaining_text}"
                if due
                else "未设置截止时间"
            )
        meta = QLabel(meta_text)
        meta.setStyleSheet("color: #48484A; font-size: 12px;")
        middle.addWidget(meta)
        layout.addLayout(middle, 1)

        bg, fg = PRIORITY_PILL.get(task.get("priority"), ("#F2F2F7", "#6E6E73"))
        pill = QLabel(task.get("priority", "中"))
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 8px;"
            " padding: 3px 9px; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)

        chevron = QLabel("›")
        chevron.setStyleSheet("color: #C7C7CC; font-size: 18px;")
        layout.addWidget(chevron, 0, Qt.AlignmentFlag.AlignVCenter)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 18))
        self.setGraphicsEffect(shadow)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_open()
        super().mousePressEvent(event)


class WindowControlButton(QPushButton):
    """自绘窗口按钮：三个图标使用一致的线宽和视觉尺寸。"""

    def __init__(
        self,
        kind: str,
        tooltip: str,
        slot,
        close: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self._close = close
        self._hover = False
        self._maximized = False
        self.setFixedSize(44, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self.clicked.connect(slot)

    def set_maximized(self, maximized: bool) -> None:
        self._maximized = maximized
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hover:
            hover_color = "#E81123" if self._close else "#E5E5E5"
            painter.fillRect(self.rect(), QColor(hover_color))
        pen_color = "#FFFFFF" if (self._close and self._hover) else "#3A3A3C"
        pen = QPen(QColor(pen_color))
        pen.setWidthF(1.25)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx = self.width() / 2
        cy = self.height() / 2
        half = 4.2
        if self.kind == "min":
            painter.drawLine(QPointF(cx - half, cy + 0.8), QPointF(cx + half, cy + 0.8))
        elif self.kind == "max":
            if self._maximized:
                painter.drawRect(QRectF(cx - 3.8, cy - 4.6, 7.6, 6.4))
                painter.drawRect(QRectF(cx - 2.0, cy - 2.8, 7.6, 6.4))
            else:
                painter.drawRect(QRectF(cx - half, cy - half, 8.4, 8.4))
        else:
            painter.drawLine(
                QPointF(cx - half, cy - half), QPointF(cx + half, cy + half)
            )
            painter.drawLine(
                QPointF(cx + half, cy - half), QPointF(cx - half, cy + half)
            )
        painter.end()


class TitleBar(QWidget):
    """无边框窗口标题栏：只保留拖动区域和右上角窗口按钮。"""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        self.min_btn = WindowControlButton(
            "min", "最小化", window.showMinimized
        )
        self.max_btn = WindowControlButton(
            "max", "最大化", window._toggle_maximize
        )
        self.close_btn = WindowControlButton(
            "close", "关闭", window.close, close=True
        )
        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

    def update_maximize_text(self, maximized: bool) -> None:
        self.max_btn.set_maximized(maximized)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._window._toggle_maximize()
        super().mouseDoubleClickEvent(event)


class WindowRoot(QWidget):
    """无边框窗口根容器：提供边缘/角落缩放。"""

    MARGIN = 6

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _edges(self, pos):
        edges = Qt.Edge(0)
        if pos.x() <= self.MARGIN:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - self.MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= self.MARGIN:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - self.MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mouseMoveEvent(self, event):
        edges = self._edges(event.position().toPoint())
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        cursor = Qt.CursorShape.ArrowCursor
        if (left and top) or (right and bottom):
            cursor = Qt.CursorShape.SizeFDiagCursor
        elif (right and top) or (left and bottom):
            cursor = Qt.CursorShape.SizeBDiagCursor
        elif left or right:
            cursor = Qt.CursorShape.SizeHorCursor
        elif top or bottom:
            cursor = Qt.CursorShape.SizeVerCursor
        self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._edges(event.position().toPoint())
            if edges != Qt.Edge(0):
                handle = self.window().windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_DISPLAY_NAME)
        self.resize(1000, 680)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self._view = config.VIEW_DUE_DATE
        self._notice = ""
        self._force_quit = False

        result = storage.initialize_user_data()
        self.settings = result["settings"]
        self.active_taskset = result["taskset"]
        if self.active_taskset is None:
            self.active_taskset = self._choose_taskset()

        # 单实例：对当前用户数据目录加锁（数据目录已由 initialize_user_data 创建）
        self._lock = QLockFile(str(config.DATA_DIR / "instance.lock"))
        if not self._lock.tryLock(100):
            raise AlreadyRunningError(
                "同一用户数据目录（%LOCALAPPDATA%\\ToDoList\\）已有实例在运行。"
            )

        self._build_ui()
        self._refresh_sidebar()
        self._setup_tray()
        self._setup_timers()
        self.refresh()
        self._process_reminders()
        self._reschedule_reminders()

    @property
    def tray_available(self) -> bool:
        return self._tray is not None

    def _make_app_icon(self) -> QIcon:
        if config.ICON_FILE.is_file():
            icon = QIcon(str(config.ICON_FILE))
            if not icon.isNull():
                self.setWindowIcon(icon)
                return icon
        # 资源缺失时的兜底图标
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#4a90d9"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPixelSize(34)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "✓")
        painter.end()
        icon = QIcon(pixmap)
        self.setWindowIcon(icon)
        return icon

    def _make_gear_icon(self) -> QIcon:
        """绘制与界面风格一致的单色齿轮图标。"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#3A3A3C"))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        center = QPointF(16, 16)
        painter.drawEllipse(center, 6.0, 6.0)
        for index in range(8):
            angle = math.radians(index * 45)
            painter.drawLine(
                QPointF(16 + 7.0 * math.cos(angle), 16 + 7.0 * math.sin(angle)),
                QPointF(16 + 9.6 * math.cos(angle), 16 + 9.6 * math.sin(angle)),
            )
        painter.drawEllipse(center, 2.4, 2.4)
        painter.end()
        return QIcon(pixmap)

    def _setup_tray(self) -> None:
        self._tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._make_app_icon(), self)
        self._tray.setToolTip(config.APP_DISPLAY_NAME)
        menu = QMenu(self)
        show_action = menu.addAction("打开主窗口")
        quit_action = menu.addAction("完全退出")
        show_action.triggered.connect(self._show_from_tray)
        quit_action.triggered.connect(self._quit_from_tray)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_timers(self) -> None:
        # 周期刷新：倒计时文字、边框等级与提醒检查（30 秒）
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._periodic)
        self._refresh_timer.start(30000)
        # 精确提醒：按下一个预定时刻单独安排一次性定时器
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setSingleShot(True)
        self._reminder_timer.timeout.connect(self._on_reminder_due)

    def _choose_taskset(self) -> dict:
        """活动任务集 ID 失效或首次无任务集时，让用户选择现有任务集。"""
        tasksets = storage.list_tasksets()
        if not tasksets:
            taskset = storage.create_taskset(config.DEFAULT_TASKSET_NAME)
            self.settings["active_taskset_id"] = taskset["taskset_id"]
            storage.save_settings(self.settings)
            return taskset
        names = [summary["name"] for summary in tasksets]
        name, ok = QInputDialog.getItem(
            self,
            "选择任务集",
            "上次活动的任务集已失效，请选择当前要使用的任务集：",
            names,
            0,
            False,
        )
        if not ok:
            name = names[0]
        picked = next(summary for summary in tasksets if summary["name"] == name)
        self.settings["active_taskset_id"] = picked["id"]
        storage.save_settings(self.settings)
        return storage.load_taskset(picked["id"])

    def _build_ui(self) -> None:
        root = WindowRoot(self)
        root.setObjectName("windowRoot")
        root_layout = QVBoxLayout(root)
        # 留出 4px 外框，既形成窗口边框，也让根容器能接收边缘缩放的鼠标事件
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(0)
        self.title_bar = TitleBar(self)
        root_layout.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root_layout.addLayout(body, 1)

        # ---------- 左侧边栏 ----------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(236)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 6, 16, 14)
        side.setSpacing(6)

        logo = QLabel()
        logo_pixmap = (
            QPixmap(str(config.LOGO_FILE)) if config.LOGO_FILE.is_file() else QPixmap()
        )
        if not logo_pixmap.isNull():
            logo.setPixmap(
                logo_pixmap.scaledToWidth(
                    150, Qt.TransformationMode.SmoothTransformation
                )
            )
        else:
            logo.setText("Tickora")
            logo.setStyleSheet("color:#1D1D1F; font-size:18px; font-weight:700;")
        logo.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        side.addWidget(logo)
        side.addSpacing(12)

        taskset_header = QHBoxLayout()
        taskset_header.setContentsMargins(0, 0, 0, 0)
        taskset_label = QLabel("任务集")
        taskset_label.setStyleSheet("color:#8E8E93; font-size:11px; font-weight:600;")
        add_taskset = QPushButton("＋")
        add_taskset.setFixedSize(22, 22)
        add_taskset.setToolTip("新建任务集")
        add_taskset.setCursor(Qt.CursorShape.PointingHandCursor)
        add_taskset.setStyleSheet(
            "QPushButton { border:none; background:transparent; color:#8E8E93;"
            " font-size:15px; border-radius:6px; }"
            "QPushButton:hover { background:#E1E1E6; color:#1D1D1F; }"
        )
        add_taskset.clicked.connect(self._create_taskset)
        taskset_header.addWidget(taskset_label)
        taskset_header.addStretch(1)
        taskset_header.addWidget(add_taskset)
        side.addLayout(taskset_header)

        self.taskset_list = QListWidget()
        self.taskset_list.setObjectName("tasksetList")
        self.taskset_list.setStyleSheet(
            "QListWidget#tasksetList { background: transparent; border: none; outline: none; }"
            "QListWidget#tasksetList::item { padding: 7px 10px; border-radius: 8px; color: #3A3A3C; }"
            "QListWidget#tasksetList::item:selected { background: #E1E1E6; color: #1D1D1F; }"
            "QListWidget#tasksetList::item:hover { background: #E9E9ED; }"
        )
        self.taskset_list.setMinimumHeight(110)
        self.taskset_list.itemClicked.connect(self._on_taskset_clicked)
        side.addWidget(self.taskset_list, 1)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setIcon(self._make_gear_icon())
        self.settings_btn.setIconSize(QSize(14, 14))
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet(
            "QPushButton { text-align:left; border:none; background:transparent;"
            " color:#3A3A3C; padding:8px 10px; border-radius:8px; font-size:13px; }"
            "QPushButton:hover { background:#E9E9ED; }"
        )
        self.settings_btn.clicked.connect(self._open_settings)
        side.addWidget(self.settings_btn)
        version = QLabel(f"版本 {config.APP_VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("color:#B0B0B5; font-size:10px;")
        side.addWidget(version)
        body.addWidget(sidebar)

        # ---------- 右侧主内容 ----------
        main_panel = QWidget()
        main_panel.setObjectName("mainPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(30, 14, 30, 14)
        main_layout.setSpacing(14)

        header = QGridLayout()
        header.setHorizontalSpacing(16)
        header.setVerticalSpacing(0)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        self.taskset_label = QLabel()
        self.taskset_label.setStyleSheet("color:#1D1D1F; font-size:26px; font-weight:700;")
        self.subtitle_label = QLabel()
        self.subtitle_label.setStyleSheet("color:#8E8E93; font-size:12px;")
        self.subtitle_label.setWordWrap(False)
        titles.addWidget(self.taskset_label)
        titles.addWidget(self.subtitle_label)
        header.addLayout(
            titles, 0, 0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        # 顶部视图切换（主内容区中间）
        self.view_switch = QFrame()
        self.view_switch.setObjectName("viewSwitch")
        switch_layout = QHBoxLayout(self.view_switch)
        switch_layout.setContentsMargins(2, 2, 2, 2)
        switch_layout.setSpacing(2)
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_buttons = {}
        for view_id, label in VIEW_LABELS.items():
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumWidth(88)
            button.clicked.connect(lambda _checked=False, v=view_id: self._set_view(v))
            self.view_group.addButton(button)
            self.view_buttons[view_id] = button
            switch_layout.addWidget(button)
        self.view_switch.setStyleSheet(
            "QFrame#viewSwitch { background: #E9E9EB; border-radius: 9px; }"
            "QPushButton { border: none; background: transparent; color: #6E6E73;"
            " padding: 6px 14px; border-radius: 7px; font-size: 12px; }"
            "QPushButton:hover { color: #1D1D1F; }"
            "QPushButton:checked { background: #FFFFFF; color: #1D1D1F;"
            " font-weight: 600; }"
        )
        header.addWidget(self.view_switch, 0, 1, Qt.AlignmentFlag.AlignCenter)
        self.add_btn = QPushButton("＋  新增任务")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(
            "QPushButton { background:#007AFF; color:#FFFFFF; border:none;"
            " border-radius:10px; padding:8px 18px; font-size:13px; font-weight:600; }"
            "QPushButton:hover { background:#0A6FE3; }"
        )
        self.add_btn.clicked.connect(self._add_task)
        header.addWidget(
            self.add_btn, 0, 2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        header.setColumnStretch(0, 1)
        header.setColumnStretch(2, 1)
        main_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 8px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #D1D1D6; border-radius: 4px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        scroll.setWidget(self.list_container)
        main_layout.addWidget(scroll, 1)

        self.notice_label = QLabel()
        self.notice_label.setStyleSheet("color:#C42B1C; font-size:11px;")
        self.notice_label.setWordWrap(True)
        self.notice_label.hide()
        main_layout.addWidget(self.notice_label)
        body.addWidget(main_panel, 1)

        root.setStyleSheet(
            f"""
            QWidget#windowRoot {{
                background: {COLORS['window']};
                border: 1px solid #DCDCE1;
                border-radius: 12px;
            }}
            QWidget#sidebar {{
                background: {COLORS['sidebar']};
                border-right: 1px solid {COLORS['sidebar_border']};
            }}
            QWidget#mainPanel {{ background: {COLORS['main']}; }}
            """
        )
        self.setCentralWidget(root)

    def _on_taskset_clicked(self, item: QListWidgetItem) -> None:
        self._switch_taskset(item.data(Qt.ItemDataRole.UserRole))

    def _set_view(self, view_id: str) -> None:
        self._view = view_id
        for vid, button in self.view_buttons.items():
            button.setChecked(vid == view_id)
        self.refresh()

    def _refresh_sidebar(self) -> None:
        if not hasattr(self, "taskset_list"):
            return
        self.taskset_list.blockSignals(True)
        self.taskset_list.clear()
        for summary in storage.list_tasksets():
            item = QListWidgetItem(summary["name"])
            item.setData(Qt.ItemDataRole.UserRole, summary["id"])
            self.taskset_list.addItem(item)
            if summary["id"] == self.active_taskset.get("taskset_id"):
                self.taskset_list.setCurrentItem(item)
        self.taskset_list.blockSignals(False)

    def _switch_taskset(self, taskset_id: str) -> None:
        if not taskset_id or taskset_id == self.active_taskset.get("taskset_id"):
            return
        if not self._save_current(show_error=True):
            self._refresh_sidebar()
            return
        try:
            taskset = storage.load_taskset(taskset_id)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self, "切换任务集失败", f"无法载入所选任务集：{exc}"
            )
            self._refresh_sidebar()
            return
        self.active_taskset = taskset
        self.settings["active_taskset_id"] = taskset_id
        try:
            storage.save_settings(self.settings)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "设置保存失败", str(exc))
        self._mark_missed_current_and_save()
        self._on_tasks_changed()
        self._refresh_sidebar()

    def _create_taskset(self) -> None:
        name, ok = QInputDialog.getText(self, "新建任务集", "任务集名称：")
        if not ok:
            return
        try:
            storage.create_taskset(name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "无法创建任务集", str(exc))
            return
        self._refresh_sidebar()

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, "title_bar"):
            self.title_bar.update_maximize_text(self.isMaximized())

    def _clear_cards(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self) -> None:
        tasks = self.active_taskset.get("tasks", [])
        view_tasks = task_manager.get_view_tasks(tasks, self._view)
        stats = task_manager.get_task_statistics(tasks)
        self.taskset_label.setText(self.active_taskset.get("taskset_name", ""))
        self.subtitle_label.setText(
            f"未完成 {stats['pending']} · 已完成 {stats['completed']}"
        )
        for vid, button in self.view_buttons.items():
            button.setChecked(vid == self._view)
        self.notice_label.setText(f"⚠ {self._notice}" if self._notice else "")
        self.notice_label.setVisible(bool(self._notice))
        self._clear_cards()
        if not view_tasks:
            empty = QLabel("今天没有待办任务\n点击右上角“＋ 新增任务”开始")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#A1A1A6; font-size:13px; padding:60px;")
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
        else:
            for task in view_tasks:
                if self._view == config.VIEW_COMPLETED:
                    due_level = "gray"
                    remaining_text = ""
                else:
                    due_level = reminder_manager.get_due_level(task)
                    remaining_text = reminder_manager.format_remaining_time(task.get("due_date"))
                self.list_layout.addWidget(
                    TaskRow(
                        task,
                        self._view,
                        due_level,
                        remaining_text,
                        on_open=lambda t=task: self._open_task(t),
                        on_toggle_completed=self._toggle_completed,
                    )
                )
            self.list_layout.addStretch(1)

    def _save_current(self, show_error: bool = True) -> bool:
        try:
            storage.save_taskset(self.active_taskset)
            return True
        except (OSError, ValueError) as exc:
            if show_error:
                QMessageBox.warning(
                    self,
                    "保存失败",
                    f"任务未能写入磁盘：{exc}\n当前改动仅保留在内存中，请检查数据目录权限后重试。",
                )
            return False

    def _add_task(self) -> None:
        dialog = TaskDialog(self.active_taskset["tasks"], parent=self)
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        self._save_current()
        # 从已完成视图新建成功后，切回默认的未完成视图
        if self._view == config.VIEW_COMPLETED:
            self._set_view(config.VIEW_DUE_DATE)
        self._on_tasks_changed()

    def _open_task(self, task: dict) -> None:
        dialog = TaskDialog(self.active_taskset["tasks"], task=task, parent=self)
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        if not dialog.was_deleted():
            self._save_current()
        self._on_tasks_changed()

    def _toggle_completed(self, task: dict) -> None:
        completed = self._view == config.VIEW_COMPLETED
        task_manager.set_task_completed(
            self.active_taskset["tasks"], task["id"], completed=not completed
        )
        self._save_current()
        self._on_tasks_changed()

    def _open_settings(self) -> None:
        if not self._save_current(show_error=False):
            answer = QMessageBox.warning(
                self,
                "任务尚未保存",
                "当前任务未能保存到磁盘。仍然打开设置并切换任务集可能丢失未保存的改动。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        dialog = SettingsDialog(
            self.settings, self.active_taskset["taskset_id"], parent=self
        )
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        old_enabled = bool(self.settings.get("reminders_enabled", True))
        self.settings = dialog.result_settings()
        new_enabled = bool(self.settings.get("reminders_enabled", True))
        if new_enabled != old_enabled:
            # 开关期间已错过的提醒键记为跳过，不补发
            self._mark_missed_current_and_save()
        selected = dialog.selected_taskset_id()
        if selected != self.active_taskset["taskset_id"]:
            self.settings["active_taskset_id"] = selected
            try:
                storage.save_settings(self.settings)
                self.active_taskset = storage.load_taskset(selected)
            except (OSError, ValueError) as exc:
                QMessageBox.critical(
                    self, "切换任务集失败", f"无法切换到所选任务集：{exc}\n仍停留在当前任务集。"
                )
                return
            # 切入的新任务集：把已经到达时刻的未处理提醒记为跳过
            self._mark_missed_current_and_save()
        self._refresh_sidebar()
        self._on_tasks_changed()

    def closeEvent(self, event) -> None:
        self._save_current(show_error=False)
        if self._force_quit or self._tray is None:
            event.accept()
            return
        if not self.settings.get("close_to_tray", True):
            event.accept()
            return
        if not self.settings.get("close_prompt_shown", False):
            box = QMessageBox(self)
            box.setWindowTitle("关闭窗口")
            box.setText("关闭主窗口后，程序可以在系统托盘继续运行并按时提醒。")
            box.setInformativeText("请选择默认行为（以后可在设置中修改）：")
            tray_btn = box.addButton("最小化到系统托盘", QMessageBox.ButtonRole.AcceptRole)
            quit_btn = box.addButton("直接退出", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(tray_btn)
            box.exec()
            self.settings["close_prompt_shown"] = True
            self.settings["close_to_tray"] = box.clickedButton() is tray_btn
            try:
                storage.save_settings(self.settings)
            except (OSError, ValueError):
                pass
            if box.clickedButton() is quit_btn:
                self._force_quit = True
                event.accept()
                return
        event.ignore()
        self.hide()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "title_bar"):
            self.title_bar.update_maximize_text(self.isMaximized())

    # ---------- 提醒调度 ----------

    def _periodic(self) -> None:
        self.refresh()
        self._process_reminders()
        self._reschedule_reminders()

    def _on_reminder_due(self) -> None:
        self._process_reminders()
        self._reschedule_reminders()

    def _on_tasks_changed(self) -> None:
        self.refresh()
        self._process_reminders()
        self._reschedule_reminders()

    def _process_reminders(self) -> None:
        if not self.settings.get("reminders_enabled", True):
            self._notice = ""
            return
        tasks = self.active_taskset.get("tasks", [])
        pending = reminder_manager.get_pending_reminders(tasks, reminders_enabled=True)
        if not pending:
            self._notice = ""
            return
        if len(pending) == 1:
            item = pending[0]
            due_display = _format_display_time(item["due_date"])
            remaining = reminder_manager.format_remaining_time(item["due_date"])
            title = item["title"]
            body = f"截止 {due_display}，剩余 {remaining}"
        else:
            names = [item["title"] for item in pending]
            shown = "、".join(names[:2])
            if len(pending) > 2:
                shown += f" 等 {len(pending)} 项"
            title = f"{len(pending)} 个任务即将截止"
            body = shown
        ok = system_integration.send_toast_notification(title, body)
        if not ok:
            detail = system_integration.get_last_toast_error()
            self._notice = (
                f"通知提交失败：{detail}" if detail
                else "通知提交失败（不影响任务数据），请检查 Windows 通知设置"
            )
            return
        self._notice = ""
        for item in pending:
            task = next(t for t in tasks if t.get("id") == item["task_id"])
            reminder_manager.mark_reminder_sent(task, item["reminder_key"])
        try:
            storage.save_taskset(self.active_taskset)
        except (OSError, ValueError):
            self._notice = "提醒记录保存失败"

    def _reschedule_reminders(self) -> None:
        now = datetime.now()
        next_time = reminder_manager.next_reminder_time(
            self.active_taskset.get("tasks", []),
            reminders_enabled=self.settings.get("reminders_enabled", True),
            now=now,
        )
        if next_time is None:
            self._reminder_timer.stop()
            return
        milliseconds = int((next_time - now).total_seconds() * 1000) + 100
        self._reminder_timer.start(max(milliseconds, 1000))

    def _mark_missed_current_and_save(self) -> None:
        if reminder_manager.mark_missed_reminders_as_skipped(
            self.active_taskset.get("tasks", [])
        ):
            try:
                storage.save_taskset(self.active_taskset)
            except (OSError, ValueError):
                pass

    # ---------- 托盘 ----------

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._force_quit = True
        if self._tray is not None:
            self._tray.hide()
        QApplication.instance().quit()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()
