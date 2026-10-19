# FlowTodo 用户网站

全新 React 官网与用户网站；入口为 `src/website.jsx`，不使用旧 `main.jsx` 和 `styles.css`。React、Vite、GSAP / ScrollTrigger、Lucide、Express、Node 内置 SQLite。

**当前正式部署**：https://app.cheemsdoge.xyz/ 使用 Cloudflare Worker + D1、邮箱验证码登录和免费 Turnstile。记录与头像按用户确认保存在 D1；桌面授权、同步、头像和设备撤销已接入。襄阳后端与四分组低价模型轮换已准备，公网官方 AI 等待网络接通。详见 [账户与同步部署状态](../docs/CLOUD_ACCOUNT_SYNC.md)。以下 Express 描述对应本地开发服务，不能代替正式部署状态。

## 本地运行

需要 Node.js 24+。在 `promo-site` 目录运行：

```powershell
npm install
npm run build
npm start
```

打开 http://127.0.0.1:4190 。页面：`/` 官网、`/pricing` 会员对比、`/register` 注册、`/login` 登录、`/demo` 访客预览、`/dashboard` 真实账户、`/roadmap` 上线规划。

开发热更新用两个终端：第一个 `$env:PORT='4180'; npm run dev:api`，第二个 `npm run dev`，浏览器打开 Vite 输出的地址（默认 5173）。Vite 的 `/api` 请求代理到 4180。

账户保存在 `promo-site/.data/accounts.sqlite`，该目录已忽略。服务器仅监听 127.0.0.1。网站账户独立于桌面软件，不读取或修改真实桌面 JSON 数据；没有共享登录、余额、AI 计次或同步桥接。

## 已实现与待接入

- 注册：服务端生成并验证一次性图像验证码，然后发送邮箱验证码；验证码 10 分钟有效、最多尝试 5 次、60 秒重发冷却。服务端检查昵称、邮箱、15–128 字符口令及条款同意。
- 登录、退出、资料保存、密码变更和会话撤销；用户与会话在 SQLite 持久化。余额由服务端返回，初始为 0。
- 密码 scrypt（N=2^17, r=8, p=1，随机盐）；限制同时最多两个 KDF；HttpOnly / SameSite 会话，生产 Secure Cookie；CSRF 令牌与 Origin 校验、接口限流、参数化 SQL、CSP、受保护的账户接口。
- 未配置 SMTP 时，本地验证码只出现在发起请求浏览器的“本地预览邮件”。常规发送接口不返回验证码；预览邮箱不对生产环境开放。
- 会员升级弹窗可以保存购买意向，但不支付、不修改会员、不增加余额。支付接口明确返回未开放。云端列表和账单是诚实的空状态。
- 所有付费额度、恢复天数、上市活动均为建议，尚未生效。桌面已有能力与云端规划在页面中分别标明。

## 会员上市建议

| 项目 | Free | Lite | Standard |
| --- | --- | --- | --- |
| 月付 | ¥0 | ¥5.99 | ¥9.99 |
| 年付 | ¥0 | ¥59.90 | ¥99.90 |
| 云端待办 | 30 | 300 | 2,000 |
| 云端任务流 | 5 | 50 | 300 |
| 云端 AI 方案 | 5 | 50 | 300 |
| 云空间 | 100 MB | 1 GB | 5 GB |
| 默认 AI 调用 | 累计试用 5 次 | 每月 100 次 | 每月 300 次 |
| 版本恢复（规划） | 本地导出 | 7 天 | 30 天 |

本地任务不受云端数量限制；Free 默认 AI 试用不按月重置，匹配当前桌面规则。年付分别优惠约 12.7% / 14.7%；建议首发首月赠送 20 / 60 次 AI 调用，活动未生效。不同模型的成本未知，付费上线前须压测与核算，不承诺无限调用。

上线顺序：可靠邮箱与生产验证码 → 手动同步、额度校验与冲突恢复 → 支付回调、订单对账与退款 → 托管 AI 计费 → 跨设备接续。降级建议保留 30 天导出窗口并限制新增，避免直接删除数据。

## 配置与上线

参考 `.env.example`，复制成 `.env` 后填写自己的服务配置。生产启动必须具备 HTTPS 的 `APP_ORIGIN`、`SMTP_HOST` / `SMTP_FROM`、`TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET`；缺失则拒绝启动。推荐由 TLS 反向代理转发到本机服务器。SMTP 强制 TLS。生产用 Cloudflare Turnstile 的服务端 hostname 校验；本地 SVG 图像验证码仅用于开发，不作为公开站点反机器人保护。

公开运营前仍须配置真实邮件并验证投递，完成云端同步、付费 AI 代理、支付与对账、自助注销 / 找回密码、数据库权限 / 备份、运营主体与支持渠道、正式条款及独立安全审查。限流目前在单进程内存中，多实例上线需共享限流存储。数据库包含邮箱等个人信息，应限制读取权限；本地版本不宣称达到生产安全认证。

安全实现参考：[OWASP 密码存储](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[OWASP 会话管理](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)、[Nodemailer SMTP](https://nodemailer.com/smtp)。

## 检查与实拍

```powershell
npm test
npm run build
```

自动测试在系统临时目录中验证验证码、重发冷却、会话隔离、越权字段、CSRF、登录限流、重启持久化、改密后所有会话失效，以及支付不扣款。测试使用注入的固定验证码，不创建预设真实账户。

官网实拍由 `../tools/capture_website.py` 从真实 QML 页面生成，使用隔离的临时示例任务、独立配置和数据目录，不读取个人任务。截图在 `public/screenshots/`，logo 来自软件现有图标。

浏览器检查覆盖官网、实拍切换、年付切换、升级弹窗、工作台、云端筛选、账单弹窗、登录注册与移动布局。尊重 `prefers-reduced-motion`，产品页签支持方向键，模态框使用原生 dialog 管理焦点。
