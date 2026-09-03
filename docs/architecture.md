# Architecture

## 分层

```text
Hermes Agent ── local OpenAI-compatible call ──> CLIProxyAPI ──> Antigravity
     │                         │
     ├─ Hermes API :8642       └─ gateway :8317
     ├─ Studio :8648
     └─ native Dashboard :9119

Standalone Status Panel :9120
  ├─ server-side, loopback-only GET probes
  ├─ reads sanitized status/model metadata
  └─ serves a static Chinese-first UI
```

Hermes Agent、Studio、CLIProxyAPI 和 Google Antigravity 属于外部运行时/服务边界；本仓库只提供集成说明、通用启动辅助和独立状态面板。不会把 Hermes Agent 或 CLIProxyAPI 的 upstream source vendor 进来。

9119 是 Hermes 原生 Dashboard，负责其原生管理界面。9120 是独立、手动启动的状态台，不加入 Core startup、systemd boot 或 Scheduled Tasks，也不会管理其他服务的生命周期。

状态面板的 model 状态来自服务端的本地数据路径和有限的 gateway catalog 读取。credential 只留在服务端；浏览器收到的状态不含 token、Authorization header、cookie 或原始配置。面板不提供 quota 集成、inference health probe、模型自动切换或配置编辑。

默认服务绑定 loopback；端口示例可由外部运行时配置，但不要把任何服务默认暴露到 `0.0.0.0`。
