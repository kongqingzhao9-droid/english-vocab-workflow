# 第三方组件

- `templates/site/vendor/supabase.js` 为 Supabase JavaScript SDK 2.49.1 的浏览器构建，沿用现有程序中的版本；上游项目：[supabase/supabase-js](https://github.com/supabase/supabase-js/tree/v2.49.1)。许可：MIT，文本见 `templates/site/vendor/LICENSE.supabase`。没有包含作者 Supabase 连接凭据。
- Python 依赖 PyMuPDF 由使用者通过 pip 安装，不将其二进制打包在此项目中。上游：[PyMuPDF](https://github.com/pymupdf/PyMuPDF)，许可信息参见其官方仓库（AGPL／商业许可）。
- Tesseract 作为可选本机 OCR 程序，由使用者单独安装，未包含其安装包。上游：[tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract)。

网站前端来自本生词本项目的页面程序，并为独立空库安装移除了作者配置与旧版迁移入口。测试数据均为合成，不包含作者私人词库。
