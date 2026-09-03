# Setup

本文使用占位符路径；请按本机实际环境替换 `<YOUR_WSL_DISTRO>`、`${HERMES_HOME}` 和 `${STATUS_PANEL_HOME}`，不要把真实 secret 写入命令历史或仓库。

## 依赖

按各外部项目的官方文档安装并登录 Hermes Agent、CLIProxyAPI 和 Google Antigravity。登录产生的 OAuth/auth store 必须留在外部项目规定的私有位置，不要复制到本仓库。

## 状态面板

Linux/WSL 示例：

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export STATUS_PANEL_HOME="${STATUS_PANEL_HOME:-$PWD/status-panel}"
export STATUS_PANEL_PYTHON="${STATUS_PANEL_PYTHON:-python3}"
bash scripts/run-status-panel.sh
```

PowerShell 示例：

```powershell
.\scripts\Start-Hermes-Status-Panel.ps1 `
  -Distro '<YOUR_WSL_DISTRO>' `
  -Helper '${STATUS_PANEL_HOME}/run-status-panel.sh'
```

`-Helper` 必须是 WSL 内的脚本路径；`-Distro` 必须是本机已安装的 WSL 发行版。脚本只启动 9120 状态面板并打开浏览器，不启动、停止或重启 Hermes Core、Studio、CLIProxyAPI 或 9119。

打开 `http://127.0.0.1:9120/`。状态面板只使用 GET 读取本地状态，默认不执行模型推理或 quota 刷新。

## 安全环境变量

示例配置使用变量名而不是 secret value，例如 `CLIPROXY_API_KEY` 和 `ANTIGRAVITY_OAUTH_CONTEXT`。请使用外部 secret manager、受限的 shell environment 或提供方官方登录机制注入它们；不要创建可提交的 `.env` 文件。

示例本地端口：CLIProxyAPI `8317`、Hermes API `8642`、Studio `8648`、native Dashboard `9119`、status panel `9120`。如需更改端口，请同步外部运行时配置和健康检查，但保持 loopback 绑定。
