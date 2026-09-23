# CLAUDE.md — 云海湾门禁系统 Home Assistant App

## 项目概述

这是一个 Home Assistant App（原称 Add-on），用于将麦驰可视对讲门禁系统的实体室内机虚拟化，实现对讲、监控、远程解锁等功能。App 名称为 **Virtual Doorlock System (VDS)**，内部包名为 `vds`。

当前版本：0.2.6 | HA 版本要求：2026.5.0+

## 项目结构

```
HA-UpperCoast-DoorLock-addon/
├── app/
│   └── vds/                  # Python 包（内部名 vds）
│       ├── __init__.py            # 包导出（公开 API）
│       ├── api.py                 # HTTP API 服务器（基于 ThreadingHTTPServer）
│       ├── call_state.py          # 呼叫状态跟踪器
│       ├── config.py              # 配置模型、默认常量、楼栋/门口机映射
│       ├── core.py                # 核心业务逻辑（IntercomCore / FrameHub）
│       ├── protocol.py             # UDP 协议编解码（JPEG 组帧、音频 PCM）
│       ├── server.py              # 入口脚本（main 函数）
│       └── store.py               # 运行时配置持久化（ConfigStore）
├── translations/
│   ├── en.yaml                   # 英文配置页翻译
│   └── zh-Hans.yaml              # 中文配置页翻译
├── config.yaml                    # App 配置 schema（HA 加载项配置页定义）
├── Dockerfile                    # Alpine Python 镜像构建
├── run.sh                         # 容器启动脚本
├── repository.yaml               # 仓库元信息
├── icon.png                       # App 图标（HA 商店显示）
├── logo.png                       # Logo
├── README.md                      # 用户使用说明
├── DOCS.md                        # App 功能文档
├── CHANGELOG.md                  # 版本变更日志
└── LICENSE                       # MIT License
```

## HA App 配置文件说明

HA App 配置使用标准 YAML 结构。以下是项目中各配置相关的文件及其对应关系：

### config.yaml（App Schema）

定义用户在 HA 配置页填写的选项，对应 HA UI 中的配置表单。

| 字段 | 类型 | 说明 |
|------|------|------|
| `building_id` | `str` | 楼栋代码，如 1A~1E、2A~2C |
| `local_id` | `str` | 本地设备 ID |
| `local_ip` | `str` | HA 主机在门禁网络中的 IP |
| `api_host` | `str` | 后端 API 监听地址，默认 0.0.0.0 |
| `api_port` | `int` | 后端 API 端口，默认 8099 |
| `api_token` | `password` | API 访问令牌 |
| `custom_device_overrides` | `list[str]` | 自定义号机覆盖列表 |

以下参数**不在 config.yaml 中显示**，因为它们是小区固定值，已内置在 `config.py` 中：

- `center_ip` — 中心地址（`192.168.16.2`）
- `property_center_ip` — 物业中心机地址（`192.168.16.3`）

### translations/zh-Hans.yaml 与 translations/en.yaml

对应 config.yaml 中每个选项的显示名称和描述，供 HA 在配置页渲染多语言标签。

### Dockerfile

使用官方 `python:alpine` 镜像，自动跟随最新 Python 版本（当前 3.13+）。

## 核心模块说明

### config.py — 配置与门口机映射

这是项目中**最重要的配置文件**，包含所有硬编码的默认值和楼栋映射：

- `DEFAULT_*` 系列常量：默认网络参数
- `BUILDING_NAMES`：楼栋 ID 与中文名称映射
- `BUILDING_IPS_BY_ID`：每个楼栋下各号机的 IP 地址
- `STATION_LAYOUT_BY_DOOR`：号机编号与名称/楼层信息
- `BUILDING_POSITION_OVERRIDES`：楼栋特定的位置描述覆盖
- `DoorStation`：门口机数据类
- `IntercomConfig`：运行时配置数据类
- `load_addon_options()`：从 `/data/options.json` 加载 HA 配置
- `normalize_options()`：合并配置来源（HA 配置 + 运行时保存 + 自定义覆盖）

### core.py — 核心业务逻辑

- `IntercomCore`：主业务类，负责 UDP 监听、呼叫处理、视频帧推送、音频流、远程解锁
- `FrameHub`：线程安全的视频帧/音频块共享中心
- 主要协议流程：监听门口机呼叫 → 建立通话会话 → 定时发送 keep-alive → 接收视频/音频 → 处理解锁/接听请求

### protocol.py — 协议编解码

定义麦驰门禁的 UDP 协议格式：

- **PENGUIN 头部**（`PENGUIN0`，ASCII 8字节）作为包标识
- **JPEG 视频帧**通过 `MonitorFrameAssembler` 组帧还原
- **音频 PCM**：8kHz / 单声道 / 16-bit little-endian
- 关键命令：`cd000100`（呼叫触发）、`b7000a00`（音频数据）、`b7000600`（解锁）

### api.py — HTTP API 服务器

基于 Python 内置 `http.server`，提供以下端点：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/status` | GET | 运行时状态和配置 |
| `/api/frame` | GET | 获取当前 JPEG 视频帧（image/jpeg） |
| `/api/unlock` | POST | 发送解锁请求 |
| `/api/answer` | POST | 接听呼叫 |
| `/api/hangup` | POST | 挂断通话 |
| `/api/audio` | GET | 获取音频 PCM 数据 |
| `/api/audio` | POST | 发送音频 PCM 数据 |
| `/api/monitor/start` | POST | 开始主动监控 |
| `/api/monitor/stop` | POST | 停止主动监控 |

### server.py — 入口点

- `main()` 从环境变量读取配置文件路径
- `UPPERCOAST_OPTIONS_PATH`（默认 `/data/options.json`）— HA 写入的配置
- `UPPERCOAST_CONFIG_PATH`（默认 `/data/uppercoast_config.json`）— 运行时持久化配置
- 依次加载配置 → 启动 IntercomCore → 启动 ApiServer → 进入主循环

### store.py — 运行时配置持久化

- `ConfigStore` 将 HA 配置与运行时配置合并后持久化到 `/data/uppercoast_config.json`
- `OPTION_CONTROLLED_KEYS` 列出由 HA 配置页控制的字段（这些字段以 HA 配置为准）

### call_state.py — 呼叫状态跟踪

- `CallStateTracker` 根据 UDP 包源 IP 匹配门口机
- 识别呼叫触发命令（`cd000100`、`98000100`、`b7000100`）和呼叫结束命令（`b4000600`）
- 丢弃不在已知门口机列表中的 UDP 包并记录日志

## 网络端口要求

App 使用**主机网络模式**，必须在 HA 主机上绑定以下 UDP 端口：

- `10000` — 门口机会话端口（接收视频帧、音频、解锁响应）
- `10008` — 门口机发现端口（发送身份认证、监控请求）

## 配置加载顺序

```
/data/options.json (HA 配置)
    ↓
config.py::load_addon_options()
    ↓
config.py::normalize_options() ← 合并 custom_device_overrides
    ↓
store.py::ConfigStore.load()
    ↓
/data/uppercoast_config.json (运行时持久化配置)
    ↓
IntercomCore + ApiServer
```

## 运行与调试

### 查看 HA App 日志

HA 的 App 日志会捕获 `stdout` 输出。App 启动时会打印：

```
门禁系统后端已启动
支持品牌：麦驰可视对讲门禁系统
楼栋：1栋A座；已加载门口机：8 个
本机 IP：192.168.16.64；室内机 ID：00010116010
后端接口：http://0.0.0.0:8099
门口机列表：1号机=192.168.16.224、2号机=192.168.16.225、...
```

### Debug 日志

v0.1.7 起，`core.py` 和 `call_state.py` 在每收到 UDP 包时会打印详细日志：

- `[core]` — 包来源、长度、命令
- `[call_state]` — 设备匹配状态

### 本地运行（容器外）

```bash
export PYTHONPATH=./app
export UPPERCOAST_OPTIONS_PATH=./config.yaml
python3 -m vds.server
```

## 支持的楼栋与门口机

| 楼栋 | 门口机数量 | 号机编号 | IP 网段 |
|------|-----------|---------|---------|
| 1栋A座 (1A) | 8 | 01~08 | 192.168.16.224+ |
| 1栋B座 (1B) | 7 | 01~07 | 192.168.18.96+ |
| 1栋C座 (1C) | 7 | 01~07 | 192.168.19.98+ |
| 1栋D座 (1D) | 8 | 01~08 | 192.168.19.219+ |
| 1栋E座 (1E) | 5 | 01~05 | 192.168.20.116+ |
| 2栋A座 (2A) | 6 | 01~06 | 192.168.21.212+ |
| 2栋B座 (2B) | 4 | 01~04 | 192.168.22.184+ |
| 2栋C座 (2C) | 7 | 01~04, 06~08 | 192.168.23.155+ |

## 相关文档链接

- 用户安装指南：[README.md](README.md)
- App 功能文档：[DOCS.md](DOCS.md)
- 版本变更日志：[CHANGELOG.md](CHANGELOG.md)
- HA App 配置文档：https://www.home-assistant.io/docs/apps/
- 仓库地址：https://github.com/CelerPi/HA-Virtual-Doorlock-System-App
