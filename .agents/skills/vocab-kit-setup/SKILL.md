---
name: vocab-kit-setup
description: 在本生词本工作流项目中初始化 Windows Codex、OneDrive 来源、ChatGPT 日常词汇对话和需要登录的空白私人网站。当用户要求初始化、配置或继续安装此试用版时使用。
---

# 初始化私人生词本

工作范围是包含本 skill 的独立项目。由本文件向上四级找到根目录，先读该目录 AGENTS.md、START_HERE.md 和 docs/SETUP.md。所有命令显式在这个根目录运行。不要调用其他同名收词工具，不修改用户其他项目或全局 skill。

## 配置流程

1. 执行 `scripts/bootstrap.ps1 -InstallDependencies`，建立本项目虚拟环境、空词库并检查依赖。若 PowerShell 阻止脚本，使用 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -InstallDependencies`，只影响本次进程。缺 Python、Git 或 OCR 时指导安装；检查并修复实际缺失项，不重装已可用依赖。后续 Python 使用 `.venv/Scripts/python.exe -B`。
2. 首次只问这句话并等待回复：“请告诉我您在云盘内用于存放pdf的文件夹名称”。用户回复后运行 `scripts/vocab.py find-pdf-folder --name <文件夹名称>`，在本机 OneDrive 同步目录里查找。找到唯一匹配且搜索完整时用该目录。若重名、目录不存在或搜索不完整，只就该问题请用户选择或确认。用户尚未建目录时，在其选定的 OneDrive 根目录创建。提示将目录设为“始终保留在此设备上”。
3. 确定 PDF 目录后，单独问：“请发给我您平时查单词的那条 ChatGPT 对话链接。”等待回复，确认是可读的原始对话，再用 `scripts/vocab.py pin-sources --pdf-directory <完整路径> --conversation <原始链接>` 把两个值固定到本技能的 `.local/sources.json`。这个文件位于本技能目录内，Git 与发行包均忽略它。已配置者复用确认过的值和进度。
4. 对话还无起点时，使用 `read_thread` 返回的最新用户消息真实 ID 运行 `scripts/vocab.py record-start --message-id <消息ID>`。只有确有逐条消息时间时才附 `--timestamp`。本次只记起点。没有可靠 ID 时报告对话未就绪并继续独立的建站准备。
5. 两个来源固定后，按 [插件配置流程](../../../docs/PLUGIN_SETUP.md) 检查 GitHub 和 Supabase 的安装状态及当前工具权限。缺少插件时提示安装，未授权时引导连接。两者分别使用已授权的工具，缺少具体操作时沿用 [手动配置流程](../../../docs/SETUP.md) 中对应步骤。授权、验证码、密码由用户本人处理。
6. 首次只使用全新独立 Supabase 项目和 GitHub 网站仓库。执行 `configure`、`prepare`、权限检查、`status`、`probe`、`publish`，成功后发布九个白名单页面文件。连接权限拒绝按 [同步流程](../../../docs/SYNC.md) 处理，并继续尚未通过的验收步骤。登录前的真实匿名检查与手机本人登录均通过后才报告配置完成。
7. 提示两个主动命令“收录试卷词汇”和“收录其他词汇”。手机网页在收录后刷新。

执行中断后根据 `.local/config.json`、`state.json` 与实际检查结果继续，避免重复新建账号、目录、项目或仓库。不要为了安装顺利而关闭 RLS 或开放匿名词库权限。
