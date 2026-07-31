# 本地视频字幕处理工具

[English README](README.md) · [贡献指南](CONTRIBUTING.md) · [安全策略](SECURITY.md) · [更新日志](CHANGELOG.md)

一个本地优先的视频字幕精修命令行工具。它将视频和可选的原始 SRT 处理为更适合播放的最终字幕：字幕文字可读、按自然意群切分、尽可能与实际语音对齐，并输出诊断、溯源、校验和人工复核报告。

## 隐私边界

- 视频、音频、画面帧和词级时间轴只在本机处理。
- 配置的 LLM 仅接收字幕文本、受保护术语和字符边界请求所必需的信息。
- 原视频和原始 SRT 保持在原位置，始终只读。
- API Key 从环境变量读取，绝不写入报告或 `pipeline_manifest.json`。

请只将有权发送给该 LLM 服务的字幕内容交给工具处理。

## 功能

- 输入诊断：检测 SRT 格式异常、重复 ID、时间倒退、重叠、顺序问题、空 cue 和可读性问题。
- 无 SRT 时，本地 Faster-Whisper 生成带词级时间的初始转写。
- 有 SRT 时，以 SRT 为文字基线；仍会进行本地词级转写，为最终重对齐提供依据。
- `--device auto` 时优先 NVIDIA CUDA；不可用时自动回退 CPU INT8。
- 通过 OpenAI 兼容的文本 LLM 完成字幕清洗和语义切点建议，并验证其 JSON 输出和术语约束。
- 支持说话人标签移除、术语保护、语义切分、词级时间对齐、可读性检查、最终 SRT、溯源、校验、复核清单和运行 manifest。

## 暂不支持

本版本不提供 GUI、批量队列、视频渲染、ASS 输出、动态字幕位置、画面分析或人工复核回写工作流。

## 前置要求

- Python 3.12（项目要求 `>=3.12,<3.14`）
- 已安装且已加入 `PATH` 的 FFmpeg 与 FFprobe
- 一个 OpenAI 兼容的 Chat Completions API 与 API Key
- 可选 NVIDIA GPU/CUDA；CPU 同样可用

### Windows 安装 FFmpeg

```powershell
winget install Gyan.FFmpeg
```

安装后请关闭并重新打开终端。如果 PowerShell 中的中文输出乱码，请先执行：

```powershell
$env:PYTHONUTF8 = "1"
```

## 安装

### 使用 uv（推荐）

```bash
git clone https://github.com/student-gps/Video-Subtitle.git
cd Video-Subtitle
uv sync --group dev
```

如果 Windows 上 uv 缓存和项目目录位于不同磁盘，可追加 `--link-mode copy`。

### 使用 pip

```bash
git clone https://github.com/student-gps/Video-Subtitle.git
cd Video-Subtitle
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install . -r requirements.txt
```

如需开发和运行测试，请安装项目本身及 `requirements-dev.txt`：

```bash
python -m pip install -e . -r requirements-dev.txt
```

## 配置 LLM

复制已提交的模板，再填写自己的值。**绝不要提交 `.env` 文件。**

```powershell
Copy-Item .env.example .env
```

```dotenv
OPENAI_API_KEY=replace_with_your_api_key
OPENAI_BASE_URL=https://your-openai-compatible-api/v1
OPENAI_MODEL=your-model-name
```

程序会从当前工作目录加载 `.env`。已有的系统环境变量优先于 `.env`。也可以使用 YAML 配置文件或命令行参数；优先级从高到低为：

1. 命令行参数：`--llm-base-url`、`--llm-model`
2. YAML 中明确配置的值
3. 系统环境变量
4. `.env` 中的值
5. 内置默认值

`OPENAI_API_KEY` 始终从 `llm.api_key_env` 指定的环境变量读取，不能也不会从 YAML 读取。

## 检查环境

```bash
uv run subtitle-pipeline doctor
# 或 pip 安装后：
subtitle-pipeline doctor
```

该命令会检查 FFmpeg/FFprobe、CUDA 回退状态和 LLM 配置完整性，但不会显示任何密钥。

## 使用方法

### 有原始 SRT

```powershell
uv run subtitle-pipeline process .\video.mp4 `
  --srt .\raw.srt `
  --glossary .\terms.txt `
  --output .\output\video-001
```

### 没有原始 SRT

```powershell
uv run subtitle-pipeline process .\video.mp4 `
  --output .\output\video-001
```

### 强制 CPU 或指定转写模型

```powershell
uv run subtitle-pipeline process .\video.mp4 `
  --output .\output\video-001 `
  --device cpu `
  --model medium
```

根据需要使用 `--language zh|en|auto`、`--config path/to/config.yaml`、`--llm-base-url`、`--llm-model`、`--keep-workdir` 和 `--overwrite`。非空输出目录默认会被拒绝；使用 `--overwrite` 时，工具只会覆盖自身的已知产物。

## 术语表

术语表可以是 UTF-8 TXT，每行一个术语：

```text
Claude Code
BMAD
GitLab
C++
Spec-Driven Design
```

也可以是 JSON 字符串数组，或带有 `terms` 数组的对象：

```json
{"terms": ["Claude Code", "BMAD", "GitLab"]}
```

术语既作为本地转写提示词，也作为 LLM 约束。若 LLM 删除已出现的受保护术语，或提议在术语内部切分，工具会拒绝该响应。

## 输出目录

```text
<output>/
├── 01_输入诊断.json
├── 02_词级时间轴.json
├── 02_原始转写.srt               # 仅无 --srt 时生成
├── 02_转写基础报告.json           # 仅无 --srt 时生成
├── 03_清洗校对.srt
├── 03_清洗修改报告.json
├── 04_语义切点.json
├── 05_意群逐句对齐.srt            # 可挂载视频的最终 SRT
├── 05_溯源报告.json
├── 05_校验报告.json
├── 05_人工复核清单.json
└── pipeline_manifest.json
```

manifest 会记录输入哈希、有效的非敏感配置、所选转写设备/模型、回退信息、产物哈希和运行状态。它不会复制源媒体或原始 SRT。

## 默认可读性规则

- 单屏中文优先约 10–26 个字符；除独立回答外，避免少于约 5 个中文字符的碎片。
- 最短展示时长为 1 秒。
- 中文警戒线为每秒 6 个汉字。
- 英文警戒线为每秒 2.5 个单词。
- 中英混排按两类文字的阅读负荷共同计算。

如果无法在不改写讲话内容或伪造时间的前提下满足规则，工具会保留结果并加入复核清单。

## 开发

```bash
uv run ruff check src tests
uv run pytest --cov=video_subtitle_pipeline
uv run python -m build
```

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发和 Pull Request 要求。

## 安全

不要公开 API Key、私密视频、音频、词级时间轴或私密字幕文本。漏洞报告方法见 [SECURITY.md](SECURITY.md)。

## 许可证

本项目使用 [MIT License](LICENSE)。
