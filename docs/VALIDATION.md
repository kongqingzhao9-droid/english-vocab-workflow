# 0.1.0 验证记录与边界

日期：2026-10-31。所有验证使用合成词、虚构账号和独立临时目录，没有向作者的正式词库写入数据。

## 已验证

- 三个 skill 通过 skill-creator 的 quick_validate。
- Python 测试验证空库起步、只记消息起点、重复初始化不重置、批次完整性和旧边界检查、无效词条失败不推进、时间精度、PDF 批次快照与变更检测、严格重复去重、Windows DPAPI 加密及目标绑定、上传失败不重试且保留本地进度、上传后确认、公开外壳白名单和发行包排除私人目录。
- 合成标注 PDF 验证紫色生词、绿色短语提取及逐页渲染；真实用户文档仍需视觉/OCR 核对。
- 使用 PGlite 0.5.14 的隔离 PostgreSQL 执行真实 SQL 模板和权限检查：匿名与陌生账号拒绝、本人读写、空库、凭证校验、追加、重复上传、禁止改删旧词、并发版本保护、保留学习状态、重复初始化不清库。
- 使用本机 Edge 与真实 Supabase SDK、模拟 API 检查：登录前不加载私人数据、错密码和陌生账号拒绝、空库四模式、320/390/1180 宽度无横向溢出、词卡与长难句、导入文本转义、打星、保存失败、归档和删除、刷新恢复、退出和会话失效锁定。
- 发行包只选择源文件，不包含 `.local`、虚拟环境、node_modules、图片/OCR 输出、Git 历史或任何已生成个人配置。另核对作者的正式 skill 和项目关键文件未被修改。

## 仍需测试者验证

新账号注册与工具授权、其 Codex 能否完整读取指定 ChatGPT 对话、实际 OneDrive 同步、用户 PDF 的视觉提取质量、真实 Supabase/PostgREST 网络行为、GitHub Pages 部署和手机本人登录。

隔离 SQL 测试不替代真实匿名 API 请求；模拟浏览器接口不代表新用户的云端权限已通过。setup skill 要逐项执行这些真实检查，不能把作者的测试结果当作用户已经配置完成。

## 复现

```powershell
python -B -m unittest discover -s tests -v
```

维护者另行准备 Node + Playwright + Edge 或 PGlite 后：

```powershell
node tests/test_browser.cjs <Playwright模块绝对路径>
node tests/test_database.cjs <PGlite模块绝对路径>
```

这些开发依赖不在用户收录流程中，不随源码发行包捆绑。运行数据库测试使用内存数据库，浏览器测试拦截全部外部请求；二者都不访问正式 Supabase。
