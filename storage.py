"""任务集与设置的本地存储（组员 D / 项目负责人负责）。

本模块只做文件读写：
- 不导入 PyQt6，不写界面逻辑，不处理任务排序或提醒判断。
- 所有路径都来自 config.py，禁止在业务代码里手写相对路径。

运行时的用户数据目录（安装版，%LOCALAPPDATA%\\ToDoList\\，由本模块按需创建）：
    %LOCALAPPDATA%\\ToDoList\\    # 可写用户数据，与程序安装目录分离
    ├── settings.json
    └── user_data/
        ├── <taskset_uuid_1>.json
        └── <taskset_uuid_2>.json

具体路径由 config.py 的 DATA_DIR / USER_DATA_DIR / SETTINGS_FILE 提供；
不把用户数据写进程序目录、当前工作目录或 PyInstaller 解包目录。

单个任务集 JSON 的结构（schema_version=2）：
{
    "schema_version": 2,
    "taskset_id": "93d659c3-b640-4fc9-9273-b5e50c118f73",
    "taskset_name": "学习任务",
    "tasks": [
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
            "completed_at": None
        }
    ]
}

开发约定：
- 任务集文件名使用 UUID，显示名称保存在 taskset_name 中。
- 读取到损坏或版本不兼容的文件时抛出明确异常，不能当成空数据覆盖。
- 保存时先写同目录临时文件，再替换目标文件。
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import config


def _taskset_path(taskset_id: str) -> Path:
    return config.USER_DATA_DIR / f"{taskset_id}.json"


def _read_json(path: Path) -> dict:
    """读取 JSON 文件；损坏时抛 ValueError，不静默当作空数据。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"文件损坏或不是合法的 UTF-8 JSON：{path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return data


def _write_json_atomic(path: Path, data: dict) -> None:
    """先写同目录临时文件，再替换目标文件；失败时保留原文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _validate_taskset(taskset: dict) -> None:
    """基本字段校验；不满足时抛 ValueError。"""
    if not isinstance(taskset, dict):
        raise ValueError("任务集必须是字典")
    if taskset.get("schema_version") != config.DATA_SCHEMA_VERSION:
        raise ValueError(
            f"任务集 schema_version 必须为 {config.DATA_SCHEMA_VERSION}，"
            f"不支持版本 {taskset.get('schema_version')} 或其他未知版本"
        )
    if not isinstance(taskset.get("taskset_id"), str) or not taskset["taskset_id"]:
        raise ValueError("任务集缺少有效的 taskset_id")
    if not isinstance(taskset.get("taskset_name"), str) or not taskset["taskset_name"].strip():
        raise ValueError("任务集名称不能为空")
    if not isinstance(taskset.get("tasks"), list):
        raise ValueError("任务集 tasks 必须是列表")


def _new_taskset_dict(name: str) -> dict:
    return {
        "schema_version": config.DATA_SCHEMA_VERSION,
        "taskset_id": str(uuid.uuid4()),
        "taskset_name": name,
        "tasks": [],
    }


def _check_name_available(name: str, exclude_id: str | None = None) -> None:
    for summary in list_tasksets():
        if summary["id"] == exclude_id:
            continue
        if summary["name"] == name:
            raise ValueError(f"任务集名称“{name}”已存在，请换一个名称")


def list_tasksets() -> list:
    """列出 user_data 目录中的所有任务集。

    返回：
        任务集摘要列表，每项至少包含 id 和 name，
        例如 [{"id": "...", "name": "我的任务"}, ...]。

    规则与边界：
        - 目录不存在时返回空列表，不创建目录。
        - 跳过损坏或版本不兼容的文件，并在界面提示。
    """
    result = []
    if not config.USER_DATA_DIR.is_dir():
        return result
    for path in sorted(config.USER_DATA_DIR.glob("*.json")):
        try:
            data = _read_json(path)
            _validate_taskset(data)
        except ValueError:
            continue  # 跳过损坏或版本不兼容的文件，由界面提示
        result.append({"id": data["taskset_id"], "name": data["taskset_name"]})
    result.sort(key=lambda item: item["name"])
    return result


def create_taskset(name: str) -> dict:
    """新建一个空任务集并保存为独立 JSON 文件。

    参数：
        name: 任务集显示名称，去掉首尾空白后不能为空，不能与现有名称重复。

    返回：
        新任务集字典（schema_version、taskset_id、taskset_name、tasks）。

    规则与边界：
        - 文件名使用新的 UUID，不使用用户输入的名称。
        - 名称为空或重复时抛出 ValueError。
        - 创建后不自动切换活动任务集。
    """
    if not isinstance(name, str):
        raise ValueError("任务集名称必须是字符串")
    name = name.strip()
    if not name:
        raise ValueError("任务集名称不能为空")
    _check_name_available(name)
    taskset = _new_taskset_dict(name)
    save_taskset(taskset)
    return taskset


def load_taskset(taskset_id: str) -> dict:
    """读取指定任务集。

    参数：
        taskset_id: 任务集 UUID。

    返回：
        任务集字典。

    规则与边界：
        - 文件不存在抛 FileNotFoundError。
        - JSON 损坏、字段缺失或 schema_version 不是 2 时抛出明确异常。
        - 只读取，不修改设置中的活动任务集。
    """
    path = _taskset_path(taskset_id)
    if not path.is_file():
        raise FileNotFoundError(f"任务集文件不存在：{path}")
    data = _read_json(path)
    _validate_taskset(data)
    return data


def save_taskset(taskset: dict) -> None:
    """保存一个任务集。

    参数：
        taskset: 完整任务集字典。

    返回：
        无返回值。

    规则与边界：
        - 保存前做基本字段校验。
        - 使用临时文件写入后替换，失败时保留原文件。
        - 写入 UTF-8 JSON，保留中文。
    """
    _validate_taskset(taskset)
    _write_json_atomic(_taskset_path(taskset["taskset_id"]), taskset)


def import_taskset(file_path: str, display_name: str | None = None) -> dict:
    """从外部 JSON 导入一个任务集副本。

    参数：
        file_path: 外部任务集 JSON 的绝对路径。
        display_name: 可选的新名称；None 表示沿用文件中的名称。

    返回：
        已保存到 user_data 的新任务集字典。

    规则与边界：
        - 一次只导入一个任务集，不合并到现有任务集。
        - 必须符合当前 schema_version=2。
        - 导入副本分配新的 taskset_id，保留任务 ID 和内容。
        - 名称与现有任务集重复时抛出 ValueError，要求重新命名。
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"要导入的文件不存在：{path}")
    data = _read_json(path)
    _validate_taskset(data)
    name = display_name
    if name is None:
        name = data["taskset_name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("任务集名称不能为空")
    name = name.strip()
    _check_name_available(name)
    new_taskset = {
        "schema_version": config.DATA_SCHEMA_VERSION,
        "taskset_id": str(uuid.uuid4()),
        "taskset_name": name,
        "tasks": data.get("tasks", []),
    }
    save_taskset(new_taskset)
    return new_taskset


def export_taskset(taskset_id: str, file_path: str) -> None:
    """把指定任务集导出为 JSON 文件。

    参数：
        taskset_id: 要导出的任务集 UUID。
        file_path: 用户选择的导出路径。

    返回：
        无返回值。

    规则与边界：
        - 导出保留原 taskset_id 和全部任务字段。
        - 写入失败时抛出异常，由界面提示。
    """
    taskset = load_taskset(taskset_id)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(taskset, f, ensure_ascii=False, indent=2)


def load_settings() -> dict:
    """读取全局设置。

    返回：
        设置字典；缺失的已知字段用 config.DEFAULT_SETTINGS 补齐。

    规则与边界：
        - settings.json 不存在时返回默认设置。
        - 文件损坏时抛出明确异常，不能静默当成首次运行。
        - 保留未知但合法的扩展键。
    """
    path = config.SETTINGS_FILE
    if not path.is_file():
        return dict(config.DEFAULT_SETTINGS)
    data = _read_json(path)
    settings = dict(config.DEFAULT_SETTINGS)
    settings.update(data)
    return settings


def save_settings(settings: dict) -> None:
    """保存全局设置。

    参数：
        settings: 设置字典。

    返回：
        无返回值。

    规则与边界：
        - 只写入已识别的设置和未知扩展键。
        - 使用临时文件替换，失败时保留原文件。
    """
    if not isinstance(settings, dict):
        raise ValueError("设置必须是字典")
    _write_json_atomic(config.SETTINGS_FILE, settings)


def initialize_user_data() -> dict:
    """首次启动时初始化缺失的用户数据。

    返回：
        {"settings": 设置字典, "taskset": 当前活动任务集字典}

    规则与边界：
        - 按需创建 DATA_DIR、user_data/、settings.json 和默认任务集。
        - user_data/ 已存在但没有任何任务集文件时，创建“我的任务”，
          并把新任务集 ID 写入 active_taskset_id。
        - 只能补建缺失的目录和文件；已存在的有效设置或任务集不得覆盖。
        - 发现损坏或不兼容 JSON 时抛出异常并保留原文件，
          不能当成空目录自动重建。
        - 不做旧数据迁移，不删除或重置任何已有任务集。
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings = load_settings()

    files = sorted(config.USER_DATA_DIR.glob("*.json"))
    valid_tasksets = []
    for path in files:
        try:
            data = _read_json(path)
            _validate_taskset(data)
        except ValueError as exc:
            # 损坏或不兼容：报错并保留原文件，绝不当作空目录自动重建
            raise ValueError(f"发现损坏或不兼容的任务集文件，已保留原文件：{path}（{exc}）") from exc
        valid_tasksets.append(data)

    if not valid_tasksets:
        # 目录为空（或没有任何任务集文件）：创建默认任务集并写入活动 ID
        taskset = _new_taskset_dict(config.DEFAULT_TASKSET_NAME)
        save_taskset(taskset)
        settings["active_taskset_id"] = taskset["taskset_id"]
        save_settings(settings)
        return {"settings": settings, "taskset": taskset}

    active_id = settings.get("active_taskset_id")
    active = next((t for t in valid_tasksets if t["taskset_id"] == active_id), None)
    if active is None:
        # 活动 ID 失效但仍有有效任务集：返回 None，由界面让用户选择，不覆盖设置
        return {"settings": settings, "taskset": None}
    return {"settings": settings, "taskset": active}
