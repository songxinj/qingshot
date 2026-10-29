# 第三方组件

本项目自行编写的代码使用 MIT 许可证。第三方组件保留各自的许可证与权利。

| 组件 / 服务 | 用途 | 官方信息 |
| --- | --- | --- |
| PySide6 / Qt for Python | 桌面窗口、图像绘制、剪贴板 | https://doc.qt.io/qtforpython-6/licenses.html |
| Windows Runtime OCR | 本机识字，依赖用户的 Windows 环境 | https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr |
| RapidOCR / ONNX Runtime | 本机文本检测和识别 | 安装包中的 rapidocr-onnxruntime 与 onnxruntime 元数据及许可证 |
| Google 翻译接口 | 用户主动请求的在线文字翻译，现有首选服务 | translate.googleapis.com |
| MyMemory | 用户主动请求的在线文字翻译 | https://mymemory.translated.net/doc/spec.php |
| Ruff（开发工具） | 静态检查与代码格式 | https://github.com/astral-sh/ruff |

当前仅交付源码，不捆绑 Python、Qt 或 Windows 组件。后续若发布安装包或独立可执行文件，需要同时检查并满足实际捆绑组件的再分发许可要求。

界面参考常见截图工具的交互习惯，图标由代码自行绘制，不包含微信商标或微信资源文件。
