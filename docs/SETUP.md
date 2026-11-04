# 初始化操作手册

本文件供 Codex 执行，测试者可以直接让 setup skill 带着做。优先使用 [插件流程](PLUGIN_SETUP.md)，本页也提供插件未就绪时的手动操作。所有命令在本项目根目录运行。下文 `python` 代表本项目 `.venv/Scripts/python.exe -B`。

## 1. 环境和来源

运行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -InstallDependencies`。它只创建本目录的虚拟环境和空词库，不安装或覆盖全局 skill。doctor 会报告 Python、PyMuPDF、Git、Tesseract 和 OneDrive 候选路径。Git 是发布网站所需；Tesseract 用于 OCR 补查。缺失项由 Codex 依据实际环境协助安装，不盲目重装。

先问“请告诉我您在云盘内用于存放pdf的文件夹名称”，收到回复后用 find-pdf-folder 在本机 OneDrive 同步目录查找。找到并确认后，单独索要原始查词对话链接。用 pin-sources 将两项固定在 setup skill 的本机专用 .local/sources.json 中。将 PDF 目录设为“始终保留在此设备上”，等待同步完成再收录。

向用户获取日常询词对话原始链接，形如 `https://chatgpt.com/c/<UUID>`。不能使用 `/share/` 快照链接。用当前 Codex 的 read_thread 工具读取最新用户消息的真实 ID，立即执行 record-start 保存来源边界。只有确有逐条消息时间时才保存时间。首次只记录起点。

## 2. 创建独立私人数据库

用户在 [Supabase](https://supabase.com/dashboard) 登录并创建**新项目**。数据库密码、登录密码由用户设置，不记录在项目或聊天。不要连接作者或用户正在使用的其他词库项目。

在 Authentication → Users 为本人创建邮箱登录账号，并确认邮箱（控制台添加用户时可选择确认）。记录该用户的 **User UID**。数据库绑定此固定 ID，不仅凭邮箱判断；其他登录账号也看不到数据。关闭允许新用户注册，保留自己的账号。

获取项目 URL 与 publishable 公钥（也支持旧 anon 公钥）。拒绝 secret key、service_role、数据库密码。执行：

```powershell
python scripts/vocab.py configure --supabase-url "https://项目引用.supabase.co" --public-key "用户项目公钥" --owner-id "本人UserUID"
python scripts/vocab.py prepare
```

configure 和 record-start 不可用示例占位值直接执行。configure 已存在且不同会拒绝改写，record-start 已存在也会拒绝重置。首次安装中断时继续已有配置，不重新选择起点而漏过中途消息。对话读取不可用时，先完成其他准备，明确对话来源尚未就绪。

prepare 在 Windows 当前账号下生成上传凭证的 DPAPI 密文，绑定数据库地址与本人 UID；生成的 SQL 仅包含凭证哈希。凭证不得进入网页、公开 Git、日志或聊天。

引导用户在**新项目** SQL Editor 中执行 `.local/setup.sql`，应看到 PRIVATE_PREPARED（0 词、0 句）和 PUBLISHER_READY。再执行 `.local/verify.sql`，应返回 PASS。SQL 可以重复执行，不清空已有词库、不覆盖学习状态；不应在每次收录时重跑。若需代填，可用用户已授权的浏览器操作读取本机生成文件，不把 SQL 内容贴进公共服务或公开仓库。

执行：

```powershell
python scripts/vocab.py status
python scripts/vocab.py probe
python scripts/vocab.py publish
```

status 必须确认授权，probe 必须确认词库和状态表匿名请求被拒绝、无效上传凭证被拒绝，空词库 publish 应得到 Already current 或 Uploaded and verified。遇到连接权限拒绝时按 [同步流程](SYNC.md) 请求只读检查，检查通过后完成尚未通过的步骤。其余错误按实际结果排查，保留已完成的配置。

## 3. 发布自己的登录页面

prepare 已生成 `.local/site/`。里面只有页面程序和 Supabase 公共连接设置，没有词库、SQL、上传凭证、UID 或密码。

优先复用用户通过 Git Credential Manager 保存的 GitHub 登录：

```powershell
python scripts/github_site.py --name my-private-vocab
python scripts/github_site.py --name my-private-vocab --apply
```

第一条只展示账号和目标；第二条创建全新公开页面仓库、只推送九个白名单文件并启用 main 根目录 Pages。用户已经请求建立网站时可直接继续，无需对每个 Git 操作重复询问。已存在且不是本工具创建的仓库会被拒绝，避免误改正式项目。GitHub 认证或网络失败不反复重试。

若电脑没有 GitHub 登录，Codex 引导用户通过 Git Credential Manager 的浏览器授权流程完成登录；不要让用户把 token 发到聊天。如果不能自动创建仓库，可引导用户在 GitHub 新建空仓库，并通过浏览器上传 `.local/site/` 的全部白名单文件（包含 vendor/supabase.js）。上传 zip 本身不会部署网页。Settings → Pages → Deploy from a branch → main / root。可使用 `site-zip` 导出干净外壳，解压后再上传。

**不要把整个生词本工作目录推送为网站。** 分享这套工具用干净发行包，分享自己的页面只用 `.local/site/`。

## 4. 首次验收

- 确认 Pages 已部署，不只看“创建仓库成功”。
- 手机打开页面，未登录只见登录框；登录本人账号显示空词库。
- 再执行 probe，确认匿名 API 被拒绝；陌生账号权限由 verify.sql 检查。
- 首次自己上传一份已标注 PDF，主动收录，刷新手机看到新词。
- 在指定对话**起点之后**问一个新词，再主动收录，确认没有导入旧历史。
- 手机试打星、归档、删除，刷新后仍保留；重新执行收录不重置状态。

手机和电脑需要能访问各自的 GitHub Pages、Supabase 和 ChatGPT 服务；网络不可达时如实报告，不能当作配置或上传成功。

## 5. 备份与故障处理

`.local/state.json` 包含本地词库和进度，`state.previous.json` 是最近一次提交前副本。它们均为私人文件。备份整个 `.local` 时自行保密；DPAPI 凭证只能在原 Windows 账号使用。换电脑或账号需要显式重新授权，不能偷偷重置凭证。

上传接口只允许追加；如果云端词库被另外修改，程序拒绝覆盖，保留本地文件，由用户和 Codex核对差异。不要用初始化 SQL 覆盖词库。网页打星、已背和删除记录保存在独立学习表，不会被追加程序写入。

若出现 `.local/operation.lock`，先确认是否仍有运行任务；只在确认前次任务已退出后删除此项目这一锁文件。不删除 state、checkpoint 或凭证来“修好”安装。
