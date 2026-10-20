"""Windows 系统集成（组员 D / 项目负责人负责）。

本模块负责两件事：
- 当前用户的开机自启查询、开启/关闭；
- Windows 原生 Toast 通知提交。

约束：
- 使用 HKEY_CURRENT_USER，不需要管理员权限。
- 不影响其他软件的自启项。
- 不导入 PyQt6，不读写任务集。
- Toast 必须是 Windows 原生通知（Windows.UI.Notifications），
  不能用 PyQt 自定义窗口或 QSystemTrayIcon.showMessage() 代替。

安装版约定：
- 开机自启使用安装版专属 Run 值名 config.AUTOSTART_RUN_VALUE_NAME
  （与旧便携版不同），只增删本应用自己的值。
- Toast 使用稳定 AppUserModelID config.APP_USER_MODEL_ID；后续 Inno Setup
  的开始菜单快捷方式必须配置相同 ID，本模块不自行创建快捷方式。
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

import config

_last_toast_error = ""


def get_last_toast_error() -> str:
    """返回最近一次 Toast 提交失败的诊断信息（成功时为空字符串）。"""
    return _last_toast_error


def _current_executable() -> str:
    """当前进程的可执行文件绝对路径（字符串比较用）。"""
    return str(Path(sys.executable).resolve())


_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _value_path(value: str) -> str:
    """从注册表值中提取目标路径（带引号的路径取引号内部分，否则取整体）。"""
    value = value.strip()
    if value.startswith('"'):
        end = value.find('"', 1)
        if end != -1:
            return value[1:end]
    return value


def get_autostart_registered_path() -> str | None:
    """返回注册表中本程序自启项记录的目标路径。

    返回：
        已登记时返回完整目标路径字符串；未登记时返回 None。

    规则与边界：
        - 只读取本程序专属的自启项。
        - 用于区分“未启用”和“已启用但路径需要修复”。
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_READ)
    except OSError:
        return None
    try:
        try:
            value, _type = winreg.QueryValueEx(key, config.AUTOSTART_RUN_VALUE_NAME)
        except FileNotFoundError:
            return None
    finally:
        winreg.CloseKey(key)
    return _value_path(str(value))


def get_autostart_state() -> bool:
    """查询本程序当前是否已正常启用开机自启。

    返回：
        只有“已登记且注册路径与当前 EXE 路径一致”时返回 True；
        未登记或路径不一致时返回 False。

    规则与边界：
        - 只检查本程序专属的注册表项名称。
        - 路径不一致说明便携文件夹被移动，界面应显示“路径需修复”。
        - 读取失败时返回 False，由界面提示实际状态。
    """
    registered = get_autostart_registered_path()
    if registered is None:
        return False
    try:
        return str(Path(registered).resolve()) == _current_executable()
    except OSError:
        return False


def set_autostart(enabled: bool, executable_path: str) -> None:
    """开启或关闭当前用户的开机自启。

    参数：
        enabled: True 表示开启，False 表示关闭。
        executable_path: 已安装程序的 EXE 绝对路径。

    返回：
        无返回值。

    规则与边界：
        - 只写入或删除本程序自己的自启项。
        - 写入路径需要加引号，避免空格导致启动失败。
        - 未打包的源码环境可抛出 RuntimeError，提示仅安装版支持。
        - 注册表操作失败时抛出异常，由界面提示。
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "源码运行环境不支持开机自启（会把 python.exe 写入注册表）；请使用安装版。"
        )
    command = f'"{executable_path}" --autostart'
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        )
    except OSError as exc:
        raise RuntimeError(f"无法打开注册表自启项：{exc}") from exc
    try:
        if enabled:
            winreg.SetValueEx(
                key, config.AUTOSTART_RUN_VALUE_NAME, 0, winreg.REG_SZ, command
            )
        else:
            try:
                winreg.DeleteValue(key, config.AUTOSTART_RUN_VALUE_NAME)
            except FileNotFoundError:
                pass  # 本来就没有，删除即完成
    finally:
        winreg.CloseKey(key)


def repair_autostart(executable_path: str) -> None:
    """修复已存在但路径失效的本程序自启项。

    参数：
        executable_path: 当前便携 EXE 的绝对路径。

    返回：
        无返回值。

    规则与边界：
        - 仅在注册表中已有本程序自启项时更新路径。
        - 如果从未开启自启，应抛出异常提示“请先开启开机自启”，
          不能借修复操作擅自开启。
        - 不修改 settings.json、user_data/ 或任务集。
    """
    # 安装版常规界面不展示修复入口；保留兼容接口。
    if get_autostart_registered_path() is None:
        raise RuntimeError("请先开启开机自启")
    if not getattr(sys, "frozen", False):
        raise RuntimeError("源码运行环境不支持开机自启操作；请使用安装版。")
    set_autostart(True, executable_path)


def send_toast_notification(title: str, body: str) -> bool:
    """提交一条 Windows 原生 Toast 通知。

    参数：
        title: 通知主标题（单任务时为任务标题，多任务时为汇总标题）。
        body: 通知正文；单任务时包含截止时间和当时剩余时间。

    返回：
        系统成功接受通知提交时返回 True；失败返回 False。

    规则与边界：
        - 必须使用 Windows 原生 Toast，不使用 PyQt 弹窗，
          也不使用 QSystemTrayIcon.showMessage() 冒充。
        - 不添加自定义操作按钮，不绑定点击任务或完成任务的逻辑。
        - 通知关闭由 Windows 提供，应用不自行绘制关闭按钮。
        - 返回 True 只表示已提交，不代表用户已经看到。
        - 失败时应提供可诊断的错误信息，界面不得误标记提醒已发送。
    """
    # 使用 windows-toasts（WinRT Windows.UI.Notifications）提交真正的系统 Toast。
    # 使用稳定 AUMID；安装版由 Inno Setup 开始菜单快捷方式携带相同 ID。
    global _last_toast_error
    _last_toast_error = ""
    try:
        from windows_toasts import Toast, WindowsToaster
    except Exception as exc:
        _last_toast_error = f"通知库不可用：{type(exc).__name__}: {exc}"
        return False
    try:
        # 与已验证可弹出的测试脚本一致：使用 WindowsToaster。
        # applicationText 作为本应用的稳定 AUMID，安装版快捷方式将配置同一 ID。
        toaster = WindowsToaster(config.APP_USER_MODEL_ID)
        toast = Toast()
        toast.text_fields = [str(title), str(body)]
        toast.attribution_text = config.APP_DISPLAY_NAME
        toaster.show_toast(toast)
    except Exception as exc:
        _last_toast_error = f"{type(exc).__name__}: {exc}"
        return False
    return True
