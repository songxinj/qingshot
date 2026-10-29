# 参与开发

目前定位为 Windows 10 / 11 上的早期版本。提交修改时，请把功能、性能和可维护性一起考虑。

## 本地环境

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python app.py
```

不需要修改系统 PowerShell 执行策略或安装系统服务。

## 提交前检查

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m unittest discover -s tests -p "test_*.py" -v
```

网络与系统 OCR 集成测试需要显式设置 `QINGSHOT_INTEGRATION=1`。普通 CI 不依赖第三方在线服务或特定 Windows OCR 语言包。

## 构建与复现

`pyproject.toml` 定义包依赖、版本来源和开发工具配置；`requirements.txt` 用于直接运行源码。需要复现已记录的 Windows / Python 3.11 环境时，可先安装 `requirements.lock.txt` 中的固定版本，再安装项目。

```powershell
.venv\Scripts\python -m pip install build
.venv\Scripts\python -m build
```

wheel 和源码包输出到 `dist/`。源码包由 `MANIFEST.in` 控制，包含公开文档、测试及夹具、工具、基准脚本与 CI 配置；本机数据和历史交付报告不在发布范围。安装后进程验证见 [验证说明](docs/verification.md)。

`tools/render_ui.py` 可重新生成文档中的四张界面预览，底图是程序绘制的测试文档。

## 仓库内容

提交前检查文件列表，保留源码、测试、公共文档、许可证及构建配置。不要提交 `data/`、`test-artifacts/`、`dist/`、`build/`、`sdist/`、虚拟环境、`.dev-tools/`、缓存、`.env` 或日志。公开报告中的链接应使用仓库相对路径，避免本机路径或依赖未提交的测试产物。

不要直接压缩整个工作目录作为源码发行包；按上述构建步骤生成源码包，并检查归档内容。`.gitignore` 只影响未跟踪文件，不能阻止打包工具读取本地文件或移除已提交的数据。

## 代码约定

- 每个模块负责一个领域；网络、磁盘存储和系统 OCR 不放进绘制逻辑。
- 优先使用命名函数、明确的状态和类型标注，避免压缩语句和大型条件分支。
- QWidget、QPixmap、QIcon 和剪贴板操作留在 GUI 线程。后台任务只操作普通数据和 QImage。
- 有阻塞风险的操作通过共享 TaskRunner 执行，不直接创建无限线程。
- 测试关注用户行为、故障处理和资源边界；不为单纯样式变化增加重复实现的测试。
- 新依赖需要说明必要性、许可证和体积影响。应用不自动安装语言包，不修改系统设置。

## 问题与变更说明

问题报告请提供 Windows / Python / PySide6 版本、显示器缩放和复现步骤。不要附上含私人信息的截图或原文。

PR 应说明触发条件、修改后的行为、验证结果，以及尚未验证的硬件条件。功能改动应更新 README；性能改动附上 `benchmarks/benchmark.py` 的前后结果。

项目采用 MIT 许可证。提交的代码必须是你有权以该许可证提供的内容。
