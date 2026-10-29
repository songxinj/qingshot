# 安全与隐私

- 截图、标注和 OCR 在本机执行。RapidOCR 直接读取内存图片，Windows OCR 回退通过标准输入接收图片，不写临时图片。
- 点击“翻译”才发送原文，不上传截图。现有服务顺序为 Google 优先；连接失败时回退到 MyMemory，此时同一段原文可能发送给两个服务。请求采用系统默认 TLS 校验，完成状态显示实际返回译文的服务。
- 应用没有自建遥测通道，初始化 RapidOCR 引擎前显式关闭 ONNX Runtime 遥测。不内置密钥，不自动修改权限、启动项、语言包或系统服务；操作系统自身的诊断行为不由本应用控制。
- 截图记录默认以普通 PNG 保存在本地，请通过偏好设置选择是否保存；程序不会自动删除既有文件。
- 源码仓库忽略 `data/` 和 `test-artifacts/`。提交前仍应检查改动，避免上传个人截图。

在线翻译使用 HTTPS GET 请求，原文放在 URL 查询参数中。翻译提供方及终止 TLS 的代理能够接触原文，请勿发送密码、令牌、个人资料或机密文件内容。MyMemory 的条款说明会长期保存提交的片段；应用调用的是 `/get` 查询接口，没有调用 `/set` 或 `/import` 公开贡献接口，但不能据此保证服务不保留查询内容。服务条款见 [MyMemory](https://mymemory.translated.net/terms-and-conditions)，OCR 运行时隐私说明见 [ONNX Runtime 1.28.0](https://github.com/microsoft/onnxruntime/blob/v1.28.0/docs/Privacy.md)。

发现安全问题后，优先使用代码托管平台的私密漏洞报告功能联系维护者；尚无私密渠道时，公开问题仅描述影响范围，避免公开敏感数据或可直接利用的细节。
