# Cloudflare 公测部署

网站：https://app.cheemsdoge.xyz/ 。管理员入口：登录后访问 `/dashboard/admin`。

2026-10-11 已发布。官网、API、数据库均在 Cloudflare，不依赖襄阳服务器的端口、Nginx、Docker 或 Tunnel。旧 `flowtodo.cheemsdoge.xyz` 隧道路由保留，其他域名记录及服务器中转服务没有改动。

## 资源与架构

- Worker：`flowtodo-website`，静态资源来自 `dist/`，仅 `/api/*` 优先经过 Worker。
- D1：`flowtodo-accounts`，ID `803882b4-8f41-467f-8789-f3963b8676c5`。
- HTTPS：Cloudflare Custom Domain 自动管理。
- Turnstile：免费 managed widget，限定网站域名；后端验证结果及 hostname。
- QQ SMTP：TLS 465。账户及授权码仅存在 Worker secrets；没有放入源代码。
- 管理员：邮箱 `3443873715@qq.com` 完成验证码验证后注册的账户。后台仅提供账户及记录统计，不提供修改余额、会员或查看他人记录内容。

## 已开放与未开放

支持邮箱验证码注册/登录、资料保存、退出全部设备、会员意向、真实余额字段、待办/任务流/AI 方案记录的创建与编辑、导出、7 天回收站、版本冲突保护，以及管理员统计。Free 每账户 30/5/5 条有效记录，单条最多 16 KB，用户数据按账户隔离。

目前是结构化记录公测，不支持图片、视频、其他附件及桌面自动同步。Lite/Standard 和 AI 调用额度是后续方案，尚未接入收费、订阅、AI 服务。余额默认为零，不生成虚假充值。计划中的 GB 空间不能理解为每个用户已经获得独立的 GB 数据库。

## 成本与容量

此次没有开通付费订阅。免费 Workers API 额度为每天 10 万请求，静态资源请求免费；D1 免费额度为账户总存储 5 GB、每日读取 500 万行及写入 10 万行，单个免费数据库上限需另外遵循 D1 limits。所有站点资源共享账户额度，不是每用户无限空间。达到限额后会影响服务，需要整理、扩容或迁移，不能保证永久免费和无限可用。QQ 邮箱仍受自身发信限制；当前应用限制全站每天最多 200 次验证码邮件、每邮箱每天 10 次、同邮箱每分钟一次。

官方资料：[Workers 价格](https://developers.cloudflare.com/workers/platform/pricing/)、[D1 价格](https://developers.cloudflare.com/d1/platform/pricing/)、[D1 限制](https://developers.cloudflare.com/d1/platform/limits/)、[Turnstile 免费计划](https://developers.cloudflare.com/turnstile/plans/)。大陆访问速度及网络可达性需要持续实测，使用 Cloudflare 不代表取得大陆备案或大陆 CDN 服务。

## 发布与维护

在 `promo-site/` 运行：

```powershell
npm test
npm run deploy:cloud
```

仅初始化空数据库时运行 `npx wrangler d1 execute flowtodo-accounts --remote --file cloud/schema.sql`。已有数据库改结构时使用经过验证的迁移，不重新建库或删除数据。Worker 发布不覆盖 D1。

使用 `npx wrangler secret put NAME` 更新 SMTP_USER、SMTP_PASSWORD、TURNSTILE_SECRET、TURNSTILE_SITE_KEY、AUTH_SECRET。不要把授权码输入到源代码或命令行参数。AUTH_SECRET 更换会使未完成的邮箱验证码失效。

D1 管理界面可查看用量并通过 Time Travel 恢复；正式运营前还需独立备份及恢复演练。导出备份含私人用户信息，应保存在受保护目录，不提交仓库。网站回收站与整库灾难恢复是不同功能。

## 验证记录

- 17 项本地测试全部通过：验证码期限/次数/用途与浏览器绑定、账号隔离、CSRF、权限、配额和版本冲突。
- Worker 实际 QQ SMTP TLS 与授权码认证成功，临时诊断 secret 已清理，诊断接口随后移除。
- 用户确认真实 QQ 邮箱注册成功；D1 确认 1 个真实账户且管理员为 1。
- 线上独立临时账户验证云端创建、读取、编辑、冲突拒绝、删除、恢复、导出、普通用户无法访问管理后台，随后清理临时账户与记录。

`cloud/live-check.mjs` 是隔离的上线存储检查；临时会话有效期 5 分钟，测试数据会自动清理。它不验证实际收信、人机验证或访问真实管理员账户。`cloud/worker.test.js` 验证业务逻辑，不能代替公网网络和邮箱送达测试。
