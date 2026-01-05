# 🎓 Scholar Agent Pro | 智能科研文献管理系统

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-red)](https://streamlit.io/)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI-green)](https://openai.com/)

**Scholar Agent Pro** 是一个全自动化的科研文献流水线工具。它集成了 **自动抓取**、**智能阅读**、**语义归档** 于一体，旨在解决科研人员“下载繁琐、整理混乱、读不完”的痛点。

只需输入一个链接，剩下的交给 AI。
---

## ✨ 核心功能

### 1. 🌐 多源智能抓取
- **ArXiv 自动清洗**：自动识别 ArXiv 摘要页链接（`/abs/`），自动转换为 PDF 直链并调用高速下载通道。
- **微信公众号/网页转 PDF**：内置 **Playwright** 浏览器引擎，支持“智能滚动”加载长图文，完美保存公众号文章为 PDF。
- **PDF 直链支持**：支持任意以 `.pdf` 结尾的 URL。

### 2. 🧠 AI 语义归档
- **智能重命名**：调用 LLM (GPT/Gemini 等) 阅读文献前 2000 字符，自动提取核心主题。
- **语义聚类**：AI 会检查“今日已建文件夹”，自动判断新文献是属于已有专题，还是需要新建分类（例如：自动将所有 *Agent* 相关论文归入同一个文件夹）。
- **去重机制**：基于 MD5 文件指纹，避免重复下载和重复消耗 Token。

### 3. 📝 自动摘要生成
- **Readme 生成**：在归档的同时，会在目标文件夹内生成/追加 `readme.txt`。
- **内容预览**：自动生成 200 字左右的中文摘要，包含发表时间、文件名及核心内容总结。

### 4. 📊 现代化可视化界面
- **Streamlit 仪表盘**：基于设计的现代化 UI。
- **实时反馈**：通过状态条实时显示下载 -> 分析 -> 归档的进度。
- **历史记录**：提供可视化的今日归档表格，支持摘要预览。
- **终端风格日志**：右侧白色日志窗口，实时监控系统后台行为。

---

## 🛠️ 安装指南

### 前置要求
- Python 3.10 或更高版本
- Chrome 浏览器（用于 Playwright 渲染）
- 可用的 OpenAI API Key（或兼容的第三方中转 Key）
- 稳定的网络环境（部分学术网站需代理）

### 1. 克隆项目
```bash
git clone [https://github.com/SeaCoast/Scholar-Agent-Pro.git](https://github.com/SeaCoast/Scholar-Agent-Pro.git)
cd Scholar-Agent-Pro

```

### 2. 安装依赖

```bash
# 安装 Python 库
pip install -r requirements.txt

# 安装 Playwright 浏览器内核 (必须执行)
playwright install chromium

```

### 3. 初始化配置

项目提供了一个配置模版，请复制并重命名：

```bash
# Linux/Mac
cp web_config.example.json web_config.json

# Windows (手动复制或使用 copy 命令)
copy web_config.example.json web_config.json

```

---

## ⚙️ 配置说明

打开 `web_config.json` 并填入你的信息：

```json
{
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx", 
    "base_url": "[https://api.openai.com/v1](https://api.openai.com/v1)",
    "model_name": "gemini-2.5-flash",
    "proxy_url": "[http://127.0.0.1:7890](http://127.0.0.1:7890)", 
    "watch_dir": "./incoming",
    "library_dir": "./MyLibrary"
}

```

* **proxy_url**: 如果你在国内，抓取 ArXiv 或调用 OpenAI 通常需要代理。请查看你的梯子软件设置（通常是 7890 或 1080）。
* **model_name**: 推荐使用 `gemini-2.5-flash` 或 `gemini-2.5-flash-nothinking`，性价比最高。

---

## 🚀 运行与使用

在终端中运行以下命令启动网页界面：

```bash
streamlit run web_assistant.py

```

启动后，浏览器会自动打开 `http://localhost:8501`。

### 使用流程

1. **输入任务**：在左侧输入框粘贴 ArXiv 链接或公众号链接。
2. **开始处理**：点击 **“🚀 开始抓取并整理”**。
3. **查看结果**：
* 观察下方的状态条流转。
* 在左下角表格查看归档结果。
* 去 `MyLibrary` 文件夹查看整理好的 PDF 和摘要。



---


## 📂 项目结构

```text
Scholar-Agent-Pro/
├── web_assistant.py      # Streamlit 主程序
├── web_config.example.json # 配置文件模版
├── requirements.txt      # 依赖列表
├── history_map.json      # AI 记忆库
├── .gitignore            # Git 忽略规则
├── incoming/             # [自动生成] 下载缓冲池
└── MyLibrary/            # [自动生成] 最终归档库

```

---

## ⚠️ 常见问题 (FAQ)

**Q: 为什么 ArXiv 下载失败？** A: 请检查 `web_config.json` 中的 `proxy_url` 端口是否与你的代理软件一致。ArXiv 在国内访问经常受限。

**Q: Windows 上报错 `NotImplementedError`？** A: 本项目代码已内置 `asyncio.WindowsProactorEventLoopPolicy()` 修复，请确保你运行的是最新版代码。

**Q: 微信公众号图片加载不全？** A: 程序内置了 `smart_scroll` 智能滚动逻辑，会模拟人类浏览行为。如果依然不全，可能是网络加载过慢，建议手动增加代码中的 `sleep` 时间。

---

