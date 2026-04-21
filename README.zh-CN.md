# Markdown Note Triage

一个以键盘操作为核心的桌面工具，用来把 Markdown 笔记快速分拣到不同分类目录，并可选接入 DeepSeek 建议分类。

## 亮点

- 直接扫描待整理目录中的 `.md` 文件
- `1-7` 快速分类，`Enter` 一键采纳建议
- 支持启动时批量预请求建议，减少逐条等待
- 结果缓存到 `<SOURCE_DIR>/.llm_cache.json`
- 同名文件自动重命名，避免覆盖
- 未配置 LLM 时也可纯手动使用

## 快速开始

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
python -m src.app
```

安装后也可以直接运行：

```powershell
md-triage
```

## 环境变量

建议先复制 `.env.example` 为 `.env`，然后至少设置：

- `SOURCE_DIR`：待整理 Markdown 目录，默认 `~/Notes`
- `SILICONFLOW_API_KEY`：可选，不填则禁用建议功能
- `LLM_MODEL`：默认 `deepseek-ai/DeepSeek-V3`，禁止 `Pro/...`

## 默认分类

| 按键 | 目录名 | 含义 |
| --- | --- | --- |
| `1` | `01_physiological` | 生活必须 |
| `2` | `02_safety` | 未来保障 |
| `3` | `03_leisure` | 娱乐享受 |
| `4` | `04_belonging` | 社交人情 |
| `5` | `05_esteem` | 自我实现 |
| `6` | `06_journal` | 心情随笔 |
| `7` | `07_reference` | 参考资料 |

## 常用快捷键

- `1-7`：移动到对应分类
- `Enter`：采纳当前建议
- `S`：跳过
- `R`：重试建议
- `Esc`：退出

## 开发命令

```powershell
pytest
ruff check .
python -m build
```

## 路线图

- [x] 键盘优先的分类 GUI
- [x] 建议缓存与启动预请求
- [ ] 外部可配置分类规则
- [ ] 首次启动目录选择器
- [ ] 多 LLM 提供方支持
- [ ] Demo GIF 与截图
- [ ] GitHub Release 桌面安装包

更多信息请看英文版 [`README.md`](./README.md)。
