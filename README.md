# 私人英语生词本工作流 · Windows 试用版

将你在 PDF 中标注的生词、短语和长难句，以及指定 ChatGPT 对话中新询问的单词，收录到自己的私人网页生词本。

**先看 [START_HERE.md](START_HERE.md)**：下载完整项目，在 Windows Codex 中打开，让初始化 skill 引导配置。

适用范围：Windows 桌面 Codex、OneDrive 本机同步目录、紫色生词／绿色短语／红色下划线长难句。Mac、其他云盘和其他标注方案不在本版承诺范围内。

## 三个 skill

| Skill | 功能 |
| --- | --- |
| `vocab-kit-setup` | 配置环境、来源、登录和空白私人网站 |
| `vocab-kit-ielts` | 主动收录标注 PDF，保留原文件 |
| `vocab-kit-other` | 主动收录指定对话新增目标词，首次只记起点 |

它们位于 `.agents/skills/`，随本项目使用，不覆盖你已有的全局 skill。

## 网站功能

记忆模式、按星级复习、字母检索、长难句解析、完整单词卡、打星、归档、删除和跨设备保存学习状态。初始没有示例词；原始 PDF 和对话不上传到 GitHub。

GitHub Pages 公开托管登录页面程序；词库和学习记录在用户自己的 Supabase 中，通过登录和数据库权限限制本人访问。页面地址可公开访问，私人数据不能仅靠“地址不告诉别人”来保护。

## 文件结构

```text
.agents/skills/        三个项目专用 skill
scripts/              初始化、提取、原子追加、上传和发布工具
templates/site/       不带个人数据的网页模板
templates/sql/        通用数据库和权限模板
docs/                 首次配置、词条格式、验证范围
tests/                独立临时目录中的合成数据测试
.local/               运行后生成；私人数据，Git 忽略，不随发行包分发
```

日常收录只更新私人数据库，不向 GitHub 推送词库。上传失败保留本地结果，下次主动收录时补传。不要把配置完成后的工作目录重新打包给别人；使用 `scripts/package_release.py` 生成干净发行包。

## 开发验证

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/package_release.py --output ../vocab-workflow-windows-v0.1.0.zip
```

界面测试需要 Node 和 Playwright，仅供维护者检查，不是用户日常使用的依赖。详见 [验证说明](docs/VALIDATION.md) 和 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 参考文档

- [Codex skills](https://learn.chatgpt.com/docs/build-skills)
- [Supabase 行级权限](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [GitHub Pages 发布设置](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

本项目尚未选定正式开源许可证；当前公开提供下载试用和反馈。第三方库遵守各自许可，详见 THIRD_PARTY_NOTICES.md。
