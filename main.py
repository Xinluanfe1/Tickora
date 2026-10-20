"""程序入口：AUMID、QApplication、单实例与 --autostart 静默启动。"""

from __future__ import annotations

import ctypes
import sys

from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

import config
from ui.main_window import AlreadyRunningError, MainWindow


def main() -> int:
    """启动应用，返回进程退出码。"""
    if sys.platform == "win32":
        # 在显示任何 Qt UI 之前设置进程 AppUserModelID（与安装版快捷方式一致）
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                config.APP_USER_MODEL_ID
            )
        except (AttributeError, OSError):
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    families = set(QFontDatabase.families())
    for family in ("Segoe UI Variable Text", "Microsoft YaHei UI", "Segoe UI", "Arial"):
        if family in families:
            font = QFont(family)
            font.setPointSize(10)
            app.setFont(font)
            break
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName(config.APP_DISPLAY_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    if config.ICON_FILE.is_file():
        app.setWindowIcon(QIcon(str(config.ICON_FILE)))

    try:
        window = MainWindow()
    except AlreadyRunningError as exc:
        QMessageBox.information(
            None, "程序已在运行", f"{exc}\n本次启动将退出。"
        )
        return 2
    except (RuntimeError, ValueError, OSError) as exc:
        QMessageBox.critical(
            None,
            "启动失败",
            f"{config.APP_DISPLAY_NAME} 无法启动：\n{exc}\n"
            "请勿删除或手动修改用户数据；如数据损坏，请先备份后再处理。",
        )
        return 1
    if "--autostart" in sys.argv and window.tray_available:
        pass  # 开机自启：静默进入托盘，不强制弹出主窗口
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
