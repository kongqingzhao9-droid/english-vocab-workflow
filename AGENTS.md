# 生词本工作流试用版

本目录是独立交付项目。只在本项目执行任务；不调用外部已安装的 vocab-collector，不读取或修改其他生词本项目。

- 仅支持 Windows 桌面 Codex、已同步至本机的 OneDrive 文件夹、紫色生词／绿色短语／红色下划线长难句。用户主动触发，不创建定时任务。
- 使用本项目 `.agents/skills/` 中的 `vocab-kit-setup`、`vocab-kit-ielts`、`vocab-kit-other`。首次使用读 START_HERE.md。
- 所有个人数据在 `.local/`：配置、词库、消息起点、PDF 进度、批次、截图、SQL、上传密文、公开网页构建产物。不得提交此目录。
- 日常询词对话初始化时只记录真实最新消息的 UTC 时间和 ID，不收历史词。已有起点绝不自动重置；来源读取不完整不推进进度。
- 程序入口为 `scripts/vocab.py`。使用本地 `.venv/Scripts/python.exe`。追加词库与推进来源进度一次原子写入；日常学习状态仅由登录网页维护。
- 收录后必须执行 publish；即使无新词也检查待上传。只在 Uploaded and verified 或 Already current 时报告已同步；上传失败不重试、不回滚已完成本地进度、不公开推送词库。
- 首次建站默认新建独立 Supabase 项目、独立网页仓库，不连接或迁移已有正式项目。登录密码由用户亲自输入，不索取；不使用 service_role、secret key 或数据库密码。
- 网站只发布 `.local/site/` 白名单文件。先检查目标新仓库的历史与文件，再推送；不要对整个工作目录 git add -A，不 force push。收录词汇不需要 Git 推送。
- 本项目没有预置用户词汇。tests 中的合成词仅供自动测试，不导入正式词库。没有完成真实 SQL、匿名请求、本人登录和手机验证，不能宣称线上全流程验收。
