# Tickora

![Tickora](resources/brand/tickora_logo.png)

Tickora 是一款面向 Windows 的本地待办清单桌面应用，基于 Python 与 PyQt6 开发。任务和设置保存在本机，不需要账号、服务器或云同步。

> **当前版本：v0.1.0（MVP / Minimum Viable Product，最小可行产品）**。这是面向本地任务管理与截止提醒的首个正式版本。

## 主要特点

- **任务管理**：新建、编辑、删除（带确认）、完成与撤销完成；支持标题、备注、优先级（高/中/低）和可选截止时间。
- **三种视图**：按截止时间、按优先级、已完成。前两个视图只显示未完成任务，已完成视图按完成时间从新到旧排列。
- **截止提醒**：每个未完成任务支持自定义提前提醒（0–10080 分钟，默认 60 分钟）和固定提前 30 分钟提醒；两个时刻重合时只提醒一次；提前 0 分钟允许 60 秒调度容差。
- **Windows 原生通知**：通过系统通知中心显示，不带任务操作按钮；主窗口隐藏到托盘后仍会检查提醒。
- **多任务集**：新建、切换、单独导入/导出 JSON 任务集；同一时间只使用一个活动任务集，切换时不会合并任务。
- **桌面集成**：系统托盘、关闭到托盘、全局提醒开关、单实例运行；开机自启默认关闭，可在安装版设置中开启。
- **本地保存**：任务自动保存，重启后恢复上次使用的任务集；每个任务集是独立的 JSON 文件。
- **界面**：左侧任务集导航、顶部三视图切换、整行任务卡片；截止紧迫度通过红/黄/白/灰边框提示。

## 系统要求

- Windows 10 / 11（64 位）。
- 安装版按当前用户安装，不需要管理员权限。
- 通知功能需要 Windows 通知服务可用；源码运行需要 Python 3.10 或更高版本。

## 下载与安装

从 GitHub Releases 下载最新安装包：

**[下载 Tickora v0.1.0](https://github.com/Xinluanfe1/Tickora/releases/latest)**

安装包文件名：`TodoList_Setup_0.1.0.exe`

1. 运行安装包，按向导完成安装。
2. 默认安装目录为 `%LOCALAPPDATA%\Programs\ToDoList`，仅当前用户使用。
3. 安装器会创建开始菜单快捷方式；桌面快捷方式可选。
4. 安装包当前没有数字签名，Windows SmartScreen 可能提示；请核对文件来源和下方 SHA-256 后再决定是否运行。

当前安装包 SHA-256：

```text
36726C00BF4DF0E60A77DFE3452CA317906DFD8FF3C0CAC9E70F254DE467ACC7
```

## 使用说明

### 任务管理

- 点击右上角「＋ 新增任务」创建任务，填写标题、优先级、备注、截止时间和提醒提前量。
- 点击任务整行打开详情，可编辑或删除；点击左侧圆形按钮标记完成。
- 使用顶部三个视图切换当前任务集的显示方式；在「已完成」视图可以撤销完成。

### 多任务集

- 左侧「任务集」用于切换不同任务集；点击右侧「＋」新建任务集。
- 在「设置」中导入/导出单个任务集；导入会生成新的任务集副本，不会覆盖已有任务集。
- 同一时间只使用一个活动任务集，切换任务集不会合并任务数据。

### 截止提醒

- 自定义提醒与固定 30 分钟提醒相互独立；两个时刻重合时只提醒一次。
- 提前 0 分钟的提醒允许最多 60 秒的调度容差；普通提醒在截止后不补发。
- 程序退出后不会发送提醒；隐藏到系统托盘时仍会继续检查。
- 通知是否显示、是否保留在通知中心，受 Windows 通知和勿扰设置影响。

### 托盘与开机自启

- 关闭主窗口时首次会询问进入系统托盘还是退出；之后按保存的选择执行。
- 托盘菜单可以重新打开主窗口或完全退出。
- 开机自启默认关闭，可在「设置」中开启；仅影响当前 Windows 用户。
- 源码运行环境不支持写入开机自启，开机自启功能需使用安装版。

## 技术栈

- Python 3.10+
- PyQt6
- JSON（`schema_version=2`）
- PyInstaller（onedir）
- Inno Setup 6

## 项目结构

```text
Tickora/
├── main.py                    # 程序入口
├── config.py                  # 版本、路径和公共常量
├── task_manager.py            # 任务增删改、完成状态与视图排序
├── reminder_manager.py        # 截止时间、提醒候选与去重
├── storage.py                 # 任务集与设置 JSON 存储
├── system_integration.py      # 开机自启与 Windows 原生 Toast
├── ui/                        # PyQt6 界面与对话框
├── resources/brand/           # Logo、应用图标
├── scripts/
│   ├── TodoList.spec          # PyInstaller onedir 配置
│   ├── installer.iss          # Inno Setup 安装器
│   └── build.ps1              # 完整构建脚本
├── tests/                     # unittest 测试
├── docs/screenshot.png        # 界面截图
├── requirements.txt           # 运行依赖
└── requirements-build.txt     # 构建依赖
```

## 从源码运行

1. 安装 Python 3.10+。
2. 安装运行依赖：

   ```text
   python -m pip install -r requirements.txt
   ```

3. 启动程序：

   ```text
   python main.py
   ```

首次运行会自动创建默认任务集「我的任务」。

## 从源码构建安装包

构建环境需要 Python 3.10+、PyInstaller 和 Inno Setup 6.2+。首次构建前执行：

```text
python -m pip install -r requirements-build.txt
winget install JRSoftware.InnoSetup
```

在项目根目录执行完整构建：

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1
```

构建结果：

- `dist/TodoList/`：完整的 PyInstaller onedir 运行目录。
- `dist_installer/TodoList_Setup_<版本>.exe`：Inno Setup 安装包。

`scripts/build.ps1` 会从 `config.py` 读取 `APP_VERSION` 并传给 Inno Setup；构建前会检查项目根目录没有 `settings.json` 或 `user_data/`。如果本机未安装 ISCC，脚本只输出安装说明，不会生成虚假的安装包。

## 用户数据

用户数据统一保存在：

```text
%LOCALAPPDATA%\ToDoList\
├── settings.json
└── user_data\
    ├── <任务集 ID>.json
    └── ...
```

数据目录名称沿用 `ToDoList` 以兼容已有任务；程序安装目录只读，不会把任务写进安装目录或项目文件夹。

**升级与卸载**：升级安装不会删除用户数据；卸载只移除程序文件、开始菜单/桌面快捷方式和安装版专属注册项，**不会删除 `%LOCALAPPDATA%\ToDoList` 中的任务数据**。如需彻底清除数据，请在确认不再需要旧任务后手动删除该目录。

## 已知限制与注意事项

- 安装包当前未做数字签名，Windows SmartScreen 可能提示；本说明不声称已签名或通过 Windows 安全认证。
- 提醒依赖 Tickora 正在运行；完全退出或电脑关机时不会发送提醒。
- 不支持搜索、账号登录、云同步、数据库、周期任务、子任务或在线更新。
- 当前仅发布 Windows 版本，任务数据不跨设备同步。
- 极端情况下，首次启动时若同时启动多个实例，可能出现两个空的默认任务集；保留有任务的一个即可。

![界面截图](docs/screenshot.png)

---

后续版本的更新计划与技术开发说明，请参阅 [《Tickora 开发说明》](安装版开发说明.md)。
