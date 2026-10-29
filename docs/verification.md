# 验证说明

本项目将离线回归、外部服务联调和真实桌面验证分开记录。生成底图的测试通过，不代表真实桌面或多屏硬件验收通过。

## 离线回归

在项目根目录运行，使用已安装开发依赖的 Python：

```powershell
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -p "test_*.py" -v
```

普通测试不依赖在线翻译服务或 Windows OCR 语言包。设置 `QINGSHOT_INTEGRATION=1` 后，测试还会调用真实 OCR 和在线翻译；只有固定测试文字会发送到服务。

| 脚本 | 覆盖范围 |
| --- | --- |
| `tests/test_app.py` | 框选、标注导出、DPI、贴图、剪贴板及主窗口 |
| `tests/test_capture_ui.py` | 图上文字编辑、工具栏及贴图菜单 |
| `tests/test_storage.py` | 设置、截图历史、后台任务及错误处理 |
| `tests/test_translation.py` | 多行、混排、分段和翻译异常 |
| `tests/test_regressions.py` | 实例竞争、窗口生命周期、快捷键、网络预算及 OCR 排版 |
| `tests/test_paths.py` | 新旧数据环境变量优先级、旧版数据目录及源码启动兼容 |

## 桌面与服务联调

```powershell
# 真实桌面采集及完整链路，需要已解锁的 Windows 交互桌面
python tests/test_desktop.py

# 生成底图，验证界面操作、真实 OCR、在线翻译、贴图和新进程配置读取
python tests/test_desktop.py --fixture
```

脚本仅框选程序生成的 `Hello world 12345` 测试窗口。结果与截图写入 `test-artifacts/`；它们是本地产物，不随源码分发。真实抓屏全黑时报告 `SKIP`，生成底图模式将采集来源标记为 fixture。

## 构建与安装验证

构建步骤见 [参与开发](../CONTRIBUTING.md)。构建 wheel 后，在项目根目录执行：

```powershell
$wheel = Get-ChildItem dist/qingshot-*.whl | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python -m pip install --no-deps --target test-artifacts/wheel-install $wheel.FullName
python tools/verify_installed.py --package-dir test-artifacts/wheel-install --data-dir test-artifacts/wheel-data
```

运行验证的 Python 需要已安装运行依赖。脚本确认模块来自安装目录、包版本与源码版本一致、声明包含 RapidOCR 且 OCR 桥接资源存在；使用独立实例名和数据目录验证第二进程唤醒、退出后重启，以及目标进程实际读取注入的偏好设置。

`MANIFEST.in` 定义源码包范围，包含公开文档、测试夹具、工具和基准脚本；排除本机设置、截图、缓存、开发工具副本及历史交付报告。构建产物保存在 `dist/`，应按版本发布，避免提交到源码仓库。

## 已记录的历史结果

### 2026-10-30：隐私修复与依赖验证

- 离线测试共 53 项，51 项通过、2 项外部服务集成测试按开关跳过；Ruff 静态检查与格式检查通过。
- 安全回归确认 ONNX Runtime 遥测在 OCR 引擎创建前关闭；使用 Pillow 13.0.0 的隔离环境验证兼容性，并以合成图片验证真实本地 OCR。
- 重新构建源码包和 wheel，核对 21 个 Python / PowerShell 模块内容一致；wheel 隔离安装后，实际进程激活、退出后重启及注入配置读取通过。源码包包含英文 README，归档未包含本机数据目录。

### 2026-10-29：开源整理与更名验证

- 项目更名为「轻映 · QingShot」，包名与命令为 `qingshot`，启动脚本为 `start.cmd`；旧数据环境变量、既有安装数据目录和单实例身份继续兼容。
- 离线测试共 52 项，50 项通过、2 项外部服务集成测试按开关跳过；Ruff 静态检查与格式检查通过。
- 源码包包含公开文档、测试夹具、工具、CI 及 OCR 资源，排除了本机数据与开发产物；可从源码包重新构建 wheel，归档内文件内容与直接构建一致。
- wheel 中的 Python / PowerShell 模块与源码一致；隔离安装后验证版本、依赖、第二进程唤醒、正常退出后重启，以及目标进程读取注入设置，全部通过。
- 启动脚本的系统 Python 与项目虚拟环境两个分支均实际启动应用，目标进程确认加载对应解释器与隔离配置，并正常退出。
- 本次未重新请求在线翻译或执行真实桌面采集；外部服务和硬件覆盖沿用下述历史边界。

### 0.2.1 历史基线

以下是 0.2.1 在 **2026-10-28** 的本地验证记录摘要，不代表当前远程 CI 状态：

- 自动化测试共 47 项：默认模式 45 项通过、2 项集成测试按开关跳过；静态与格式检查通过。
- wheel 隔离安装、第二进程唤醒和退出后重启通过；新进程确认读取 `remember=false` 与 `copy_shortcut=Ctrl+PageUp`。
- RapidOCR 从内存生成图片识别到 `Hello world 12345`；真实 Google HTTPS 翻译及生成底图的完整界面联调通过。
- MyMemory 回退分支由受控连接失败与响应覆盖，不将其记为真实服务可用性验证。
- 单屏 125% DPR 有本地验证；真实桌面采集在当时环境中全黑，报告为 `SKIP`。

历史原始测试目录不属于公开源码；重新执行上述脚本可生成本次环境的结果。

## 性能与硬件边界

`python benchmarks/benchmark.py` 测量历史枚举、界面填充和带标注导出的耗时，输出本机数据。脚本会在 `test-artifacts/` 创建 10,000 个基准文件；结果受磁盘、系统负载和图像尺寸影响。

混合 DPI 多屏、HDR、受保护视频及远程桌面尚无完整硬件覆盖。大桌面底图和极长笔迹可能增加内存或重绘耗时。线程、缓存和网络预算见 [架构文档](architecture.md)。
