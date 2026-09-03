# Hermes + Antigravity Local Stack

> Local Hermes Agent runtime, an OpenAI-compatible model gateway, and a standalone read-only status panel.

这是一个面向本机部署的集成参考仓库：Hermes Agent 负责 Agent runtime，CLIProxyAPI 负责本地 OpenAI-compatible model gateway，Google Antigravity 作为模型后端，独立的 9120 状态面板提供只读可观测性。本仓库提供集成方法、通用启动脚本、脱敏示例和状态面板；它不是 Hermes Agent、CLIProxyAPI 或 Antigravity 的源码镜像，也不包含任何认证数据。

## 架构

```text
浏览器
  ├─→ Hermes Studio :8648
  ├─→ Hermes 原生 Dashboard :9119
  └─→ Standalone Status Panel :9120  (只读 GET)

Hermes Agent runtime
  └─→ CLIProxyAPI gateway :8317  ──→ Google Antigravity
                                  (OAuth 由外部依赖自行管理)
```

示例端口为 `8317` gateway、`8642` Hermes API、`8648` Studio、`9119` native Hermes Dashboard 和 `9120` standalone status panel；这些端口均应视为可配置值，并且本地服务应只绑定 loopback。

## 本仓库包含什么

- `status-panel/`：独立的只读状态面板。数据由服务端读取并以有限的 JSON 状态返回。
- `scripts/`：通用的手动启动脚本，不负责启动、停止或修改 Hermes Core。
- `examples/`：从零手写的配置模板，只引用环境变量名和占位符。
- `docs/`：分层架构、设置和安全排障说明。

Hermes Agent、CLIProxyAPI 和 Google Antigravity 都是外部依赖。仓库不 vendor 它们的完整源码，不包含运行时数据库、日志、备份、state、PID/lock 文件或浏览器 profile。

状态面板只读：不做 quota 自动查询，不做模型 inference probe，不向 Antigravity 发起浏览器侧请求，也不把 credential 放入浏览器响应或前端状态。请不要把真实配置、OAuth、API key 或 cookie 提交到 Git。

## 快速开始

1. 按外部项目的官方文档安装 Hermes Agent、CLIProxyAPI 和 Google Antigravity，并在它们各自的安全位置完成登录。
2. 复制示例配置，替换 `<PLACEHOLDER>`，并通过环境变量提供本机路径和 secret；不要把值写进仓库。
3. 设置 `STATUS_PANEL_HOME` 指向本仓库的 `status-panel` 目录，设置 `STATUS_PANEL_PYTHON` 指向已安装依赖的 Python。
4. 手动运行 `scripts/run-status-panel.sh`，或使用 PowerShell 脚本并传入 `-Distro` 和 `-Helper`。
5. 浏览器打开 `http://127.0.0.1:9120/`。9119 native Dashboard、8648 Studio 和其他依赖按外部项目方式单独管理。

通用路径示例：`${HERMES_HOME}`、`${STATUS_PANEL_HOME}` 和 `%USERPROFILE%`。本仓库不依赖任何特定用户、Windows 账户、WSL 发行版或绝对目录。

## English summary

This repository documents a local Hermes Agent + CLIProxyAPI + Google Antigravity integration and ships a standalone, loopback-only, read-only status panel. Upstream runtimes and OAuth remain external dependencies. No credentials, runtime state, logs, databases, backups, or upstream source trees are included.

## 安全提示

Never commit credentials. 提交前请检查 `.env`、OAuth token、API key、API_SERVER_KEY、Authorization header、cookie、auth store、原始日志和数据库；发现误提交时立即停止共享并按 `SECURITY.md` 处理。

本项目未添加开源许可证；如需公开分发，请先单独决定许可证和第三方资源归属。
