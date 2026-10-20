"""storage 的读写测试：全部使用临时隔离目录，绝不触碰真实 AppData。"""

import json
import os
import tempfile
import unittest
from pathlib import Path

_TMP_ENV = tempfile.mkdtemp(prefix="todolist_storage_env_")
os.environ["LOCALAPPDATA"] = _TMP_ENV

import config
import storage
import task_manager


class StorageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="todolist_storage_test_")
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        config.DATA_DIR = base / "ToDoList"
        config.USER_DATA_DIR = config.DATA_DIR / "user_data"
        config.SETTINGS_FILE = config.DATA_DIR / "settings.json"

    def _active_file(self) -> Path:
        settings = storage.load_settings()
        return config.USER_DATA_DIR / f"{settings['active_taskset_id']}.json"

    def test_initialize_creates_default_taskset_and_settings(self):
        result = storage.initialize_user_data()
        taskset = result["taskset"]
        self.assertEqual(taskset["taskset_name"], config.DEFAULT_TASKSET_NAME)
        self.assertEqual(taskset["schema_version"], 2)
        self.assertEqual(taskset["tasks"], [])
        self.assertTrue(config.SETTINGS_FILE.is_file())
        self.assertEqual(
            result["settings"]["active_taskset_id"], taskset["taskset_id"]
        )

    def test_user_data_not_written_next_to_program(self):
        storage.initialize_user_data()
        self.assertFalse((config.APP_DIR / "settings.json").exists())
        self.assertFalse((config.APP_DIR / "user_data").exists())
        self.assertTrue(config.SETTINGS_FILE.is_file())

    def test_restart_persistence(self):
        result = storage.initialize_user_data()
        taskset = result["taskset"]
        task_manager.add_task(taskset["tasks"], "持久化任务", due_date="2026-10-20T09:00:00")
        storage.save_taskset(taskset)
        storage.save_settings({"active_taskset_id": taskset["taskset_id"], "reminders_enabled": False})

        # 模拟重启：重新从磁盘读取
        reloaded = storage.load_taskset(taskset["taskset_id"])
        self.assertEqual(len(reloaded["tasks"]), 1)
        self.assertEqual(reloaded["tasks"][0]["title"], "持久化任务")
        self.assertIsNone(reloaded["tasks"][0]["completed_at"])
        reloaded_settings = storage.load_settings()
        self.assertFalse(reloaded_settings["reminders_enabled"])
        self.assertEqual(reloaded_settings["active_taskset_id"], taskset["taskset_id"])

    def test_corrupt_taskset_raises_and_is_not_overwritten(self):
        storage.initialize_user_data()
        path = self._active_file()
        original = path.read_bytes()
        path.write_bytes(b"not json at all")
        with self.assertRaises(ValueError):
            storage.load_taskset(storage.load_settings()["active_taskset_id"])
        with self.assertRaises(ValueError):
            storage.initialize_user_data()
        self.assertEqual(path.read_bytes(), b"not json at all")
        self.assertNotEqual(path.read_bytes(), original)

    def test_corrupt_settings_raises_and_is_not_overwritten(self):
        storage.initialize_user_data()
        config.SETTINGS_FILE.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            storage.load_settings()
        self.assertEqual(config.SETTINGS_FILE.read_text(encoding="utf-8"), "{broken")

    def test_duplicate_taskset_name_raises(self):
        storage.initialize_user_data()
        storage.create_taskset("学习")
        with self.assertRaises(ValueError):
            storage.create_taskset("学习")
        with self.assertRaises(ValueError):
            storage.create_taskset("  学习  ")
        with self.assertRaises(ValueError):
            storage.create_taskset("   ")

    def test_import_assigns_new_id_and_detects_conflict(self):
        storage.initialize_user_data()
        external = {
            "schema_version": 2,
            "taskset_id": "93d659c3-b640-4fc9-9273-b5e50c118f73",
            "taskset_name": "外部任务集",
            "tasks": [
                {
                    "id": "31594232-239b-4d40-9319-65f4527796f3",
                    "title": "外部任务",
                    "description": "",
                    "priority": "中",
                    "status": "未完成",
                    "due_date": None,
                    "reminder_minutes_before": 60,
                    "reminder_configured_at": "2026-10-18T15:20:00",
                    "reminder_sent_keys": [],
                    "created_at": "2026-10-18T15:20:00",
                    "updated_at": "2026-10-18T15:20:00",
                    "completed_at": None,
                }
            ],
        }
        source = Path(self._tmp.name) / "external.json"
        source.write_text(json.dumps(external, ensure_ascii=False), encoding="utf-8")
        imported = storage.import_taskset(str(source))
        self.assertNotEqual(imported["taskset_id"], external["taskset_id"])
        self.assertEqual(imported["tasks"][0]["id"], "31594232-239b-4d40-9319-65f4527796f3")
        with self.assertRaises(ValueError):
            storage.import_taskset(str(source))

    def test_export_roundtrip(self):
        result = storage.initialize_user_data()
        taskset = result["taskset"]
        task_manager.add_task(taskset["tasks"], "导出任务")
        storage.save_taskset(taskset)
        out = Path(self._tmp.name) / "exported.json"
        storage.export_taskset(taskset["taskset_id"], str(out))
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["taskset_id"], taskset["taskset_id"])
        self.assertEqual(data["tasks"][0]["title"], "导出任务")

    def test_list_tasksets_skips_corrupt_files(self):
        storage.initialize_user_data()
        storage.create_taskset("第二个任务集")
        (config.USER_DATA_DIR / "broken.json").write_text("garbage", encoding="utf-8")
        names = [summary["name"] for summary in storage.list_tasksets()]
        self.assertIn("第二个任务集", names)
        self.assertIn(config.DEFAULT_TASKSET_NAME, names)
        self.assertEqual(len(names), 2)


if __name__ == "__main__":
    unittest.main()
