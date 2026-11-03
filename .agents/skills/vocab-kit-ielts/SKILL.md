---
name: vocab-kit-ielts
description: 在已配置的本生词本工作流项目中，用户主动说“收录试卷词汇”“处理新文件”“处理试卷”时，从其 OneDrive 文件夹收录标注 PDF 的生词、短语和长难句并上传私人网站。不处理其他生词本项目，不定时检测。
---

# 收录试卷词汇

由本文件向上四级定位项目根目录，读 AGENTS.md 和 docs/ENTRY_SCHEMA.md。所有命令在这个根目录执行，解释器为 `.venv/Scripts/python.exe -B`。检查 `.local/config.json`、`.local/state.json`，未初始化时引导使用本项目 setup skill，不借用外部词库或已安装的旧 skill。

1. 执行 `scripts/vocab.py scan`。它按修改时间扫描配置目录，并保存本批文件清单和内容指纹；不改处理进度。无新 PDF 时仍执行 publish 以补传未同步词库。
2. 对清单内每个 PDF 执行 `scripts/extract_pdf.py "完整PDF路径" --out ".local/extracted/<本批ID>/<文件序号>"`。脚本无需改源码，输出逐页 JSON 与渲染图。
3. 紫色高亮是生词；红色下划线是长难句；绿色高亮是短语，只为其中目标生词建卡，完整短语放 phrase，例如 on behalf of 只做 behalf。对照每页渲染图检查缺词、跨行短语和句子边界。文字层缺词或无文字时，用 Tesseract 对渲染图 OCR 补查：`tesseract <图路径> <输出前缀> -l eng`；可使用安装目录中的 exe。不得把提取为空直接当作没有标记，也不把未标注词自动收录。
4. 与 `.local/state.json` 的已有词、本批候选去重，忽略大小写，并结合语义核对 s/es/ed/d/ing 等变体，例如 construed 和 construe。不要机械去后缀误合并不同词。保留已有词条及顺序，网页中的星级、已背和删除状态不能被收录覆盖。
5. 根据 schema 生成完整词条和长难句解析，按 PDF 时间顺序排列。例句优先来自原文，需明确是自拟例句时不要冒称真题。词根词缀不得强行拆解；无合适拆分可注明整体记忆。
6. 写 `.local/batch.json`，source 使用 `kind: "pdf"`、scan 返回的 `manifest_id`、`complete: true`；vocab 和 sentences 包含新增条目，已确认重复可不填。只有本批所有 PDF 与渲染/OCR 核对完成才标记 complete。执行 `scripts/vocab.py apply --batch .local/batch.json`，原子保存词库与本批处理进度。文件处理中发生改变会拒绝推进，此时重新扫描核对；失败不能手工改进度绕过。
7. 执行 `scripts/vocab.py publish`。只有 Uploaded and verified 或 Already current 才报告已同步，提示刷新私人网页。网络、授权或追加冲突失败时保留本地词库和已提交进度，报告待上传，不自动重试、不推送公开 Git，也不重建 SQL 绕过。下次即使无新 PDF 也再次调用 publish。

保留原 PDF，不删除或移动；不创建自动化任务。报告新增词/句、重复项和无法确认的标记，不把未读页视为无词。
