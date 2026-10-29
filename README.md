# 轻映 · QingShot

轻巧截图，随手标注，让画面表达更清楚。

使用 PySide6 实现的 Windows 桌面截图工具，支持框选标注、置顶贴图、本地 OCR 和在线文字翻译。

当前版本 **0.2.1 · Alpha**，源码采用 MIT 许可证。项目采用标准 `src` 布局，包含静态检查、回归测试、Windows CI 和性能基准。

![截图与图上文字编辑](docs/assets/capture-ui.png)

界面采用单排图标工具栏、按需展开的颜色面板和图上文字编辑。更多预览见 [界面说明](docs/ui-reference.md)，版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 安装与启动

需要 **Windows 10 / 11、Python 3.11 或更新版本**。下载源码并解压，或克隆仓库后，在项目根目录运行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python app.py
```

安装后也可运行 `.venv\Scripts\qingshot`。以上命令直接调用虚拟环境中的 Python，无需激活环境或修改 PowerShell 执行策略。

若使用已有的 Python 环境，也可以安装依赖后直接启动：

```powershell
python -m pip install -r requirements.txt
python app.py
```

`start.cmd` 使用项目的 `.venv`（存在时），否则使用系统 Python。更新前先从系统托盘退出旧版本，避免单实例机制唤起旧进程。

项目提供源码和 Python wheel 的构建方式，尚未提供独立 EXE。wheel 仍需 Python，依赖由 pip 安装。构建与开发说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。

`requirements.lock.txt` 记录 Windows / Python 3.11 的已验证依赖版本，可用于复现环境；普通安装采用 `pyproject.toml` / `requirements.txt` 中的兼容范围。

## 截图

1. 点击“开始截图”，或按全局快捷键 **Ctrl + Alt + A**。
2. 拖动框选区域；主窗口和已有贴图会暂时隐藏，完成后恢复。
3. 在浮动工具栏选择矩形、圆形、箭头、画笔、文字或马赛克。支持调整颜色、线宽和撤销。
4. 选择完成复制、贴图、识字/翻译或保存 PNG。

文字工具直接在选区内输入；Enter 确认文字，Shift+Enter 换行，Esc 放弃当前文字。输入文字时 Ctrl+C / Ctrl+Z 操作文字本身。颜色和小、中、大尺寸仅在选择标注工具时展开；鼠标悬停图标可查看功能和快捷键。

在“框选”工具下，拖动选区内部可以移动选区，拖动四角可以调整大小，拖动外部可以重新框选。

| 快捷键 | 操作 |
| --- | --- |
| Ctrl + Alt + A（可在偏好设置修改） | 全局开始截图 |
| Enter / 双击选区 | 完成并复制 |
| Esc / 右键 | 取消截图 |
| Ctrl + Z | 撤销标注 |
| Ctrl + C（可在偏好设置修改） | 完成并复制 |
| Ctrl + S（可在偏好设置修改） | 保存截图 |
| Ctrl + P（可在偏好设置修改） | 完成并贴图 |

若微信等其他应用占用了默认全局快捷键，工作台与偏好设置会明确提示，可在“偏好设置”中直接点击输入框录制新的全局截图快捷键及完成复制、贴图、保存快捷键（支持冲突校验、失败自动回滚及一键恢复默认）；仍可从按钮和系统托盘截图。取消或完成截图、创建贴图均不会将后台主工作台强行弹到前台。

截图会按显示器逻辑坐标合成桌面，使用最高显示器缩放倍率导出，并支持跨屏选区。单屏 125% 缩放已实测；混合 DPI 多显示器未在本机硬件上实测，低 DPI 屏幕部分会放大到统一倍率。

## 贴图

- 截图后点击“贴图”，或在工作台点击“贴到桌面”。
- 也可从剪贴板创建贴图，双击截图记录可以重新贴图。
- 贴图保持置顶；拖动移动，滚轮缩放，Ctrl + 滚轮调整透明度。
- 双击或 Esc 关闭；Ctrl + C 复制原始图片，Ctrl + S 保存。
- 右键可复制、保存、识字/翻译，以及恢复原始大小和透明度。

## 识字与翻译

1. 截图时选择“识字/翻译”，或从工作台、贴图右键菜单进入。
2. 应用优先调用 RapidOCR，按原有规则回退到 Windows OCR，在本机提取文字，不上传图片。
3. 检查、修改原文，选择目标语言，然后点击“翻译”。
4. 译文可一键复制；也支持直接粘贴文字翻译。

**只有点击“翻译”才发送原文文字**，本地识字不会请求在线翻译。服务顺序为 Google 优先，连接失败时回退到 MyMemory，同一段原文可能发送给两个服务；完成状态显示实际返回译文的服务。服务存在额度、网络和翻译质量限制；联网失败、额度不足会显示错误，可保留原文后重试。

原文自动判断支持中、英、日、韩，其他语言请手动选择；目标语言支持中文、英语、日语、韩语、法语、德语、西班牙语。自动判断为简单文字特征判断，短句和混合语言可能需要手动修正。

多行内容按行判断原文语言并保持空行、缩进及换行；重复行共用一次请求，最多同时发出 3 个翻译请求。OCR 不再改动已选择的目标语言。原文与目标语言相同时会提示调整，服务只返回原文时会报告未生成译文，不会提示翻译成功。

Windows 本地识字优先使用进程内缓存的 **RapidOCR（PP-OCRv4 ONNX）** 引擎，直接识别内存 PNG 并根据文本框坐标还原同行拼接与段落空行。当环境未安装 RapidOCR 或指定特殊系统语言包时，回退至 **Windows 自带 OCR**；系统回退依赖可用的 OCR 语言包。

## 数据与退出

- 截图记录默认保存到本目录的 `data/captures/`，最多在界面列出最近 200 张；不会自动清理文件。
- 可在“偏好设置”关闭自动保存。关闭后，之后的截图仅保留在当前内存、剪贴板或你指定的保存位置；既有文件保留。
- 设置保存为 `data/settings.json`，异常写入 `data/app.log`。
- 源码启动默认使用本项目的 `data/`；安装 wheel 后默认使用 `%LOCALAPPDATA%/QingShot/`；检测到旧版 `%LOCALAPPDATA%/QingCapture/` 时沿用旧目录。也可通过环境变量指定目录。
- 关闭主窗口默认留在系统托盘；右键托盘选择“退出轻映”才能完全退出。可在设置中关闭托盘驻留。
- 重复启动会唤起已运行的工作台。
- `QINGSHOT_DATA` 环境变量可指定其他数据目录；兼容旧版 `QINGCAPTURE_DATA`，两者同时设置时优先使用新变量。

## 验证

```powershell
# 回归测试：框选、DPI 导出、标注、贴图、配置、任务池和错误处理
python -m unittest discover -s tests -p "test_*.py" -v

# 加上真实 Windows OCR 与在线翻译请求
$env:QINGSHOT_INTEGRATION = '1'
python -m unittest discover -s tests -p "test_*.py" -v

# 真实桌面截图 → 本地 OCR → 在线翻译 → 贴图 → 新进程读取设置
python tests/test_desktop.py

# 无法访问交互桌面时，用生成的底图验证界面操作与真实 OCR / 网络链路
python tests/test_desktop.py --fixture

# 可复现的本机性能基准
python benchmarks/benchmark.py
```

桌面测试只框选程序生成的 `Hello world 12345` 白底测试窗口；测试结果和界面截图保存在 `test-artifacts/`。桌面测试需要已解锁的 Windows 桌面，会短暂显示测试窗口。

测试范围、历史验证结果和硬件覆盖限制见 [验证说明](docs/verification.md)。`--fixture` 使用生成的底图，不计为真实桌面采集验证；混合 DPI 多屏尚无硬件实测。

## 文件

| 文件 | 用途 |
| --- | --- |
| `app.py` | 源码目录启动入口 |
| `src/qingshot/application.py` | 应用启动、单实例和日志 |
| `src/qingshot/main_window.py` | 工作台和功能协调 |
| `src/qingshot/overlay.py` / `pin.py` | 框选标注和置顶贴图 |
| `src/qingshot/translation_dialog.py` | 可编辑原文与翻译界面 |
| `src/qingshot/ocr.py` / `translation.py` | 本地 OCR 与在线文字翻译 |
| `src/qingshot/resources/ocr.ps1` | Windows Runtime 内存图片桥接 |
| `src/qingshot/storage.py` / `history.py` / `workers.py` | 配置、历史缩略图和有界任务池 |
| `tests/` / `benchmarks/` | 回归测试、联调脚本和性能基准 |
| `.github/workflows/ci.yml` | Windows Python 3.11 / 3.12 检查与打包配置 |
| `tools/` | 实际界面预览生成与安装后进程验证 |
| `docs/` | 架构、界面预览与验证说明 |
| `MANIFEST.in` / `.gitignore` | 源码包文件范围与本地文件忽略规则 |

## 开源与维护

请阅读 [MIT 许可证](LICENSE)、[参与开发](CONTRIBUTING.md)、[安全与隐私](SECURITY.md) 和 [第三方组件说明](THIRD_PARTY_NOTICES.md)。CI 配置已提供，本地验证不代表远程 CI 已通过。

`data/`、`test-artifacts/`、虚拟环境、缓存、构建目录及本地开发工具不属于公开源码。提交或分发前应检查实际文件列表；直接压缩整个工作目录会包含被 `.gitignore` 忽略的文件。

实现依据：[Qt 屏幕截图与 DPI 文档](https://doc.qt.io/qtforpython-6.11/PySide6/QtGui/QScreen.html)、[Microsoft Windows OCR 文档](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.trycreatefromuserprofilelanguages)、[MyMemory API 规格](https://mymemory.translated.net/doc/spec.php)。翻译请求按官方单次 500 字节上限拆分。
