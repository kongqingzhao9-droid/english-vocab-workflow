# 同步私人词库

在试用项目根目录用 `.venv/Scripts/python.exe -B` 执行 `scripts/vocab.py publish`。即使本轮无新增，也检查待上传内容。只有返回 `Uploaded and verified` 或 `Already current` 才报告已同步，并提示刷新私人网页。

| 错误 | 处理 |
| --- | --- |
| `NETWORK_ACCESS_DENIED`，例如 WinError 10013 | 当前环境拒绝连接。按下面的只读检查流程处理 |
| `NETWORK_DNS`、`NETWORK_TIMEOUT`、`NETWORK_TLS` 或 `NETWORK_CONNECTION` | 报告实际错误，保留本地记录，等待网络恢复后补传 |
| API HTTP 401 或 403 | 请求已经收到 HTTP 拒绝。核对项目和上传授权 |
| 其他 HTTP 错误、词库追加冲突或线上校验失败 | 报告具体结果并保留本地记录。按问题排查项目、接口或词库状态 |

## 连接权限被拒绝

1. 使用当前 Codex 环境提供的正常授权流程，对同一项目发起一次 `scripts/vocab.py status` 只读检查。说明本次只检查网络与发布授权，查询不发送词库内容。环境需要联网审批时，使用命令工具正式支持的审批方式。
2. 只有检查返回 `Publisher authorized`，才在已授权的网络环境下继续执行一次 `scripts/vocab.py publish`。写入若需要单独批准，按工具提示申请。同步仍使用本地保存的词库，并由脚本复核远端结果。
3. 审批被拒绝或不可用、只读检查失败，或本次补传仍失败时，停止并报告“本地已保存，线上同步未确认”及原因。保留词库、PDF 进度和对话起点，下次主动收录时检查补传。不要重复执行失败操作、重新提取本批、改安全策略、重置发布授权或改走 GitHub 上传。

`status` 的成功结果表示发布接口可访问且凭证被接受。若上传请求或回读验证时断线，云端可能已收到写入。应以随后一次正常 publish 的校验结果为准。
