# Security

本仓库默认按本地私有部署资料处理。不要提交真实凭据，也不要把凭据放在 issue、commit message、截图、日志或发布附件中。

## 绝不提交的内容

- OAuth access token、refresh token、API key、API_SERVER_KEY、client secret、password 或 private key。
- `Authorization`/`Bearer` header、cookie、浏览器 profile、auth store、session storage 或账号标识。
- 真实 `config.yaml`、`.env`、token/credential 文件、原始请求/响应、运行日志、备份、state、数据库、PID/lock 文件。
- 特定机器的用户名、邮箱、绝对 home path、WSL VHDX 路径、SID、session/task ID 或本机进程信息。

仓库中的 `key_env`、`*_ENV`、`*_CONTEXT` 等只是变量名，不是 secret value。真实值应在运行环境的安全存储中提供，并让程序只在需要时于内存中读取。

## 发现泄露时

1. 立即停止 push、分享和自动化任务。
2. 从工作区和暂存区移除泄露内容；不要只删除当前文件而忽略 Git history。
3. 立即旋转受影响的 credential，并按提供方文档撤销旧 credential。
4. 若内容已进入远端 history，保留事件时间线并执行经过审查的 history rewrite；必要时联系仓库管理员和提供方。
5. 重新执行敏感模式、PII 和高熵字符串审计，再决定是否恢复发布。

本仓库只提交 example/template，不提交真实 `config.yaml`。发布可见性、许可证和第三方资源归属需要单独审查。
