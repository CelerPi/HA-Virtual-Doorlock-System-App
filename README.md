# 云海湾门禁系统 — Home Assistant App

![version](https://img.shields.io/badge/version-v0.2.6-blue)
![ha-version](https://img.shields.io/badge/HA-2026.5.0%2B-41BDF5)

麦驰可视对讲门禁系统的 Home Assistant App（原称 Add-on），将实体室内机虚拟化，实现对讲、监控、远程解锁等功能。

## 功能

- 虚拟室内机运行与监听
- 门口机呼叫监听与弹窗提醒
- 视频实时监控
- 远程解锁
- 通话接听与挂断

## 安装

1. 在 Home Assistant 中，进入 **设置 → 应用 → 应用商店**
2. 点击右上角菜单 → **仓库**
3. 添加仓库地址：`https://github.com/CelerPi/HA-Virtual-Doorlock-System-App`
4. 商店刷新后，找到 **Virtual Doorlock System (VDS)** 并安装

## 配置

安装完成后，在应用的 **配置** 标签页中填写以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `building_id` | 楼栋标识 | `1A`（对应1栋A座） |
| `local_id` | 本地设备ID | `00010116010` |
| `local_ip` | 本机IP地址 | `192.168.16.64` |
| `api_host` | API监听地址 | `0.0.0.0` |
| `api_port` | API监听端口 | `8099` |
| `api_token` | API访问令牌 | （可选） |
| `custom_device_overrides` | 自定义号机覆盖 | `01:192.168.16.224` |

> **默认网络参数说明**：中心地址（`192.168.16.2`）和物业中心机地址（`192.168.16.3`）为本小区固定值，已内置在代码中，无需在配置页填写。如果你的小区网络环境不同，请手动编辑 `app/vds/config.py` 中的 `DEFAULT_CENTER_IP` 和 `DEFAULT_PROPERTY_CENTER_IP` 常量。

> **自定义号机覆盖说明**：默认情况下 App 会根据你选择的楼栋自动加载门口机 IP。如果你需要覆盖某些号机的 IP，请在 `custom_device_overrides` 中添加，格式为 `号机编号:IP地址`（如 `01:192.168.16.224`）。App 启动时会自动校验号机是否属于当前楼栋，格式错误或号机不合法的项会被忽略并记录日志。不需要覆盖的号机留空即可。

## API 接口

App 启动后会提供以下 HTTP 接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/status` | GET | 运行时状态和配置 |
| `/api/frame` | GET | 获取当前 JPEG 视频帧 |
| `/api/unlock` | POST | 解锁门口机 |
| `/api/answer` | POST | 接听呼叫 |
| `/api/hangup` | POST | 挂断通话 |
| `/api/audio` | GET | 获取接收到的音频 PCM 数据（参数：`?since=audio_id`） |
| `/api/audio` | POST | 发送音频 PCM 数据到门口机 |
| `/api/monitor/start` | POST | 开始主动监控指定门口机 |
| `/api/monitor/stop` | POST | 停止主动监控 |
| `/api/ws` | WebSocket | 实时状态、视频帧和音频通道 |

## 音频格式

音频采样参数为 **8kHz / 单声道 / 16-bit little-endian PCM**。

- `GET /api/audio` 返回 `{"ok": true, "audio_id": N, "chunks": [{"id": N, "pcm": "base64"}]}`，每个 chunk 是一段 PCM 数据。
- `POST /api/audio` 请求体为 `{"target_ip": "...", "pcm": "base64..."}`，PCM 数据需为偶数字节长度。

## 注意事项

- 本 App 使用 **主机网络模式**，需要在 HA 主机上绑定 UDP `10000` 和 `10008` 端口
- 当前仅支持 **麦驰可视对讲门禁系统**
- 支持架构：`aarch64`、`amd64`

## 版本日志

详见 [CHANGELOG.md](CHANGELOG.md)
