---
name: vocab-kit-setup
description: 在本生词本工作流项目中初始化 Windows Codex、OneDrive 来源、ChatGPT 日常词汇对话和需要登录的空白私人网站。当用户要求初始化、配置或继续安装此试用版时使用。
---

# 初始化私人生词本

工作范围是包含本 skill 的独立项目。由本文件向上四级找到根目录，先读该目录 AGENTS.md、START_HERE.md 和 docs/SETUP.md。所有命令显式在这个根目录运行。不要调用其他同名收词工具，不修改用户其他项目或全局 skill。

## 配置流程

1. 执行 `scripts/bootstrap.ps1 -InstallDependencies`，建立本项目虚拟环境、空词库并检查依赖。若 PowerShell 阻止脚本，使用 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -InstallDependencies`，只影响本次进程。缺 Python、Git 或 OCR 时指导安装；检查并修复实际缺失项，不重装已可用依赖。后续 Python 使用 `.venv/Scripts/python.exe -B`。
2. 询问 OneDrive 收录目录和日常询词的原始 ChatGPT 对话链接。可以从 OneDrive 环境变量发现本机同步根目录，向用户建议在其中创建“英语生词本/待收录PDF”；用户选择后创建，不擅自选择多个 OneDrive 账号。提示将目录设为“始终保留在此设备上”。不要求用户公开分享文件夹或对话。
3. 通过当前 Codex 的 `read_thread` 能力读取指定对话最新消息，获取真实 UTC 时间和消息 ID。这里**只建立起点，不提取任何旧词**。若权限、消息时间或 ID 不可靠，停留在“来源未配置”，保留其他完成项，不能用当前时间或猜测值替代。已有起点时保持它，继续安装绝不重新记录。
4. 默认每人新建自己的 Supabase 项目和新 GitHub 网页仓库。根据 docs/SETUP.md 利用可用工具或浏览器尽量代劳；账号注册、验证码、密码输入交给用户。索要项目 URL、publishable/anon 公钥和已确认登录账号的 User UID，不索取密码、service_role、secret key 或管理密钥。
5. 执行 `vocab.py configure` 保存用户配置，再用真实来源消息执行 `record-start`。执行 `prepare` 生成一次性 `.local/setup.sql`、`.local/verify.sql` 和公开页面外壳。引导用户在其新项目 SQL Editor 执行 setup.sql 与 verify.sql；确认结果，不把生成 SQL 或密文上传到 GitHub。若工具可安全代填 SQL，可代劳，密码仍由用户输入。
6. 运行 `status`、`probe`、`publish`；空库同步也应成功。上传失败保留本地状态，不反复重试。通过 `github_site.py --name <新名称>` 查看将发布的目标，再在用户已授权建立网站的范围内加 `--apply` 创建独立仓库、推送白名单页面并启用 Pages。若无 Git 登录，帮助用户通过 Git Credential Manager/浏览器登录；不要索取 token 明文。不要重用已存在的正式仓库。
7. 检查网站部署、手机本人登录与空词库显示。不要导入示例词。只有 SQL 权限检查、真实匿名拒绝、上传确认和本人登录都通过，才报告配置完成。提示两个主动命令：“收录雅思词汇”“收录其他词汇”；无定时任务，手机网页收录后需刷新。

执行中断后根据 `.local/config.json`、`state.json` 与实际检查结果继续，避免重复新建账号、目录、项目或仓库。不要为了安装顺利而关闭 RLS 或开放匿名词库权限。
