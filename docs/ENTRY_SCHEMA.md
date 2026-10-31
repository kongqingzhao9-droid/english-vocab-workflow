# 词条与批次格式

最终词库由程序保存在 `.local/state.json`，结构为 `library: {vocab: [], sentences: []}`。不要手工覆盖完整词库或网页学习表；生成新增批次后执行 apply。

新词必备内容：word、phonetic、pos、defEn、meanings（字符串数组）、usage、example、exampleCn、prefix、root、suffix、synonyms（字符串数组）、derivatives（字符串数组）、phrase。无合适词根拆分可写“整体记忆”，不要编造。order、stars、archived 由追加程序分配为递增编号、0、false。

新句必备内容：original、translation、main、clauses（字符串数组）。id 由程序分配递增数字。完整句子重复时保留原条目。

以下仅示范结构，不导入空词库。请用真实提取结果替换说明文字：

```json
{
  "source": {
    "kind": "chat",
    "conversation_id": "与配置一致的对话UUID",
    "previous": {"timestamp": "当前checkpoint的原始时间字符串", "id": "当前checkpoint的原始ID"},
    "upper": {"timestamp": "读取开始时最新来源消息的真实UTC时间", "id": "该消息真实ID"},
    "complete": true
  },
  "vocab": [
    {
      "word": "实际目标词", "phonetic": "音标", "pos": "词性",
      "defEn": "Concise English definition", "meanings": ["中文释义"],
      "usage": "常用搭配与用法", "example": "完整英语例句", "exampleCn": "例句翻译",
      "prefix": "前缀或无", "root": "词根或整体记忆", "suffix": "后缀或无",
      "synonyms": [], "derivatives": [], "phrase": "来源短语或空字符串"
    }
  ],
  "sentences": []
}
```

PDF 批次只替换 source：

```json
{"kind": "pdf", "manifest_id": "scan生成的批次UUID", "complete": true}
```

complete 表示整个批次已读完，所有标记都已生成词条或确认重复。图片没看完、OCR 有缺口、对话没读到旧边界时不能标 true。不要用模型推测的消息时间生成上界。

apply 会自动处理严格大小写重复，但词形变体（s/es/ed/d/ing 等）需要模型结合上下文核对后去重，避免把不同词误并。批次为空但已完整处理来源时也可以 apply，随后仍运行 publish。

所有批次、提取结果、页图和 OCR 输出只能存入 `.local/`。它们可能含整页真题或对话内容，不随 GitHub 项目公开。
