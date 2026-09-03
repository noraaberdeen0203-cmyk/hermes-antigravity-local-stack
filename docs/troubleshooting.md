# Troubleshooting

## localhost 或 proxy 问题

- 对 `127.0.0.1`、`localhost` 和 `::1` 的请求应显式绕过代理，并确认服务监听 loopback。
- 检查 `NO_PROXY`/`no_proxy` 是否保留既有值并覆盖 localhost；不要把 proxy URL、用户名或密码写入日志。
- 仅用状态码、MIME 和脱敏摘要诊断；不要复制原始请求/响应。

## model_not_found

- 先核对外部 CLIProxyAPI 的 live catalog 与 provider 的精确 route ID。
- 区分显示名、别名、reasoning preset 和真实 base model；不要根据回答风格推断模型身份。
- 保持凭据、模型路由和默认值不变，直到有明确的配置级证据。

## CSS asset link

- 从 `index.html` 的实际 `link rel="stylesheet"` 和 `script src` 开始检查。
- 直接 GET 静态资源，核对 200、正确 MIME 和响应体不是 HTML fallback。
- 检查 `Cache-Control`、base href 和 Service Worker 痕迹；只有证据表明浏览器使用旧资源时才加 cache bust。
- 不要为了修复前端静态资源修改 API schema、provider、OAuth 或运行时启动链。

## 其他安全边界

状态面板是只读可观测性工具。它不做 quota 自动查询、inference probe、自动 fallback、模型自动切换或配置编辑。遇到认证失败时，请回到外部项目的官方登录流程，不要手工复制 token。
