# 更新日志

## 0.2.6 - 2026-09-23

- **修复 WebSocket 正常断开时 addon 报 `NameError`**
  - `api.py` 补充导入 `aiohttp` 模块，确保 `aiohttp.ClientConnectionError` 可以被正确捕获
  - 避免手机 App、浏览器刷新、切后台或监控切换时日志出现 `NameError: name 'aiohttp' is not defined`

## 0.2.5 - 2026-06-13

- 统一仓库命名为 `HA-Virtual-Doorlock-System-App`。
- 同步 README、配置元数据和仓库地址中的 GitHub 链接。

## 0.2.4 - 2026-06-01

- **修复 WebSocket 客户端断开时 addon 报错**
  - 前端页面刷新、关闭或移动端切后台时，不再向已关闭 WebSocket 写入数据
  - 接收循环遇到正常断开时安静退出，避免 `Cannot write to closing transport`

## 0.2.3 - 2026-06-01

- **WebSocket 媒体流改为二进制传输**
  - 视频帧直接发送 `VDSF + frame_id + JPEG bytes`
  - 音频帧直接发送 `VDSA + audio_id + PCM bytes`
  - 移除实时媒体流中的 JSON/base64 编码开销，降低前端解码压力

## 0.2.2 - 2026-06-01

- **优化实时 WebSocket 媒体推送**
  - 推帧循环从 50ms 调整为 20ms，避免限制实机约 27fps 视频流
  - 状态消息改为低频推送，不再随每个 `frame_id` / `audio_id` 变化反复发送
  - 降低前端解析压力，改善实时画面卡顿

## 0.2.1 - 2026-05-31

- **区分呼叫与监控会话类型**
  - `FrameHub.begin_call()` 新增 `session_type` 参数（`"call"` / `"monitor"`）
  - `snapshot()` 返回 `session_type`，供 Integration 区分呼入与主动监控
  - 主动监控时不再触发呼入弹窗，避免监控画面被呼叫弹窗覆盖
- **新增实时 WebSocket 通道**
  - 新增 `/api/ws`，统一推送状态、视频帧和接收音频数据
  - Dashboard 卡片和手机端可优先使用实时通道，降低轮询延迟
  - WebSocket 支持 Header Token 和 `?token=` 两种鉴权方式
- **升级 API 服务实现**
  - API 服务从 `http.server` 迁移到 `aiohttp`
  - 保留原有 REST 接口，兼容现有 Integration 和旧版卡片
  - Dockerfile 新增 `aiohttp` 依赖安装

## 0.1.9 - 2026-05-30
- **给每个状态都添加了日志输出**
  - 很多奇怪的错误终于可以查日志找到问题所在了

## 0.1.8 - 2026-05-30
- **删除Apparmor.txt**
  - Apparmor.txt会造成莫名其妙的安装错误。
  
## 0.1.7 - 2026-05-29

- **添加运行时 debug 日志，便于排查呼叫接收问题**
  - `core.py` 每收到一个 UDP 包都会打印 `src IP:port`、`length`、`command`
  - `call_state.py` 在丢弃未知源 IP 的包时打印已知门口机列表
  - 在 Addon 日志中可直接观察到是否收到了门口机的呼叫数据包

## 0.1.6 - 2026-05-29

- **基础镜像升级至最新 Python**
  - Dockerfile 基础镜像从 `python:3.12-alpine` 升级为 `python:alpine`（自动追踪最新 Python 版本，当前为 3.13+）
  - 国内镜像源保留在注释中，Docker Hub 无法访问时可快速切换
- **`building_id` 配置项使用英文简写，便于用户填写**
  - `config.yaml` 中 `building_id` 为 `str` 类型，配置页显示为文本输入框
  - 使用英文简写（1A~1E、2A~2C）替代中文（1栋A座等），避免输入错误
  - `config.py` 同时兼容旧版中文配置（如 `1栋A座`）和新的英文简写（如 `1A`）
- **`custom_device_overrides` 兼容字符串类型输入**
  - `config.py` 的 `normalize_options()` 增加对字符串类型的兼容处理
  - 当 `custom_device_overrides` 被 HA 保存为字符串而非列表时，自动包装为单元素列表

## 0.1.4 - 2026-05-29

- **重构号机配置为自定义覆盖列表，加入防呆校验**
  - 将 8 个独立的 `door_01_ip` ~ `door_08_ip` 输入框合并为 `custom_device_overrides` 字符串列表
  - 每项格式为 `号机编号:IP地址`（如 `01:192.168.16.224`），只添加需要覆盖的号机
  - Addon 启动时自动校验：
    - 格式错误（缺少冒号分隔）的条目会被跳过并记录 warning
    - 不属于当前楼栋的号机会被跳过并记录 warning（如 1栋E座 尝试覆盖 6号机会被拒绝）
  - 合法覆盖项正常生效，不合法项不影响 Addon 启动

## 0.1.3 - 2026-05-29

- **隐藏固定网络参数，简化配置页**
  - `center_ip`（中心地址 `192.168.16.2`）和 `property_center_ip`（物业中心机 `192.168.16.3`）已从 `config.yaml` 配置页中移除
  - 改为在 `config.py` 中通过 `DEFAULT_CENTER_IP` 和 `DEFAULT_PROPERTY_CENTER_IP` 硬编码
  - 如果你的小区网络环境不同，请手动编辑 `app/vds/config.py` 后重新安装 App

## 0.1.2 - 2026-05-29

- **恢复楼栋下拉菜单**
  - `config.yaml` 中 `building_id` 的 schema 从 `str` 改回 `list`
  - 下拉菜单可单选楼栋，保存后 `normalize_options()` 自动取列表第一项作为字符串
  - 同时解决之前 `str` 类型下无法下拉选择的问题

## 0.1.1 - 2026-05-29

- 修复 `building_id` 配置不生效导致号机数量不随楼栋变化的问题
  - `config.yaml` 中 `building_id` 的 schema 从 `list` 改为 `str`，避免 HA 将其保存为数组
  - `config.py` 的 `normalize_options` 增加对列表类型的防御处理，取第一项

## 0.1.0 - 2026-05-27

- 初始发布：Home Assistant App 版本
- 仓库地址：https://github.com/CelerPi/HA-Virtual-Doorlock-System-App
- 将应用目录、应用标识和 Python 包名统一为 `vds`
- 加载项名称：Virtual Doorlock System (VDS)
- 当前仅支持麦驰可视对讲门禁系统
- 楼栋下拉选项为中文楼栋名，保存并重启后加载对应门口机配置
- 启动日志输出为中文摘要，不再输出完整 JSON 配置
- 配置页、应用说明、使用文档均使用中文命名
- 提供 `/health`、`/api/status`、`/api/frame`、`/api/unlock`、`/api/answer`、`/api/hangup` 等 HTTP 接口
