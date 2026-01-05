import streamlit as st
import os
import json
import time
import threading
import asyncio
import sys
import hashlib
import shutil
import re
import random
import httpx
import pandas as pd
from datetime import datetime
from openai import OpenAI
from playwright.async_api import async_playwright

# === Windows 平台异步修复 ===
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ================= 1. 全局配置与状态管理 =================

CONFIG_FILE = "web_config.json"
HISTORY_DB = "history_map.json"
DEFAULT_CONFIG = {
    "api_key": "sk-xxxx",
    "base_url": "https://api.openai.com/v1",
    "model_name": "gpt-4o-mini",
    "proxy_url": "http://127.0.0.1:7897",
    "watch_dir": "./incoming",
    "library_dir": "./MyLibrary"
}

# 初始化 Session State
if "logs" not in st.session_state: st.session_state.logs = []
if "monitor_running" not in st.session_state: st.session_state.monitor_running = False
if "thread_obj" not in st.session_state: st.session_state.thread_obj = None
if "stop_event" not in st.session_state: st.session_state.stop_event = threading.Event()
if "history_records" not in st.session_state: st.session_state.history_records = []


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            pass
    return DEFAULT_CONFIG


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.insert(0, f"{timestamp} | {message}")
    if len(st.session_state.logs) > 100: st.session_state.logs.pop()


def add_history_record(filename, folder, summary):
    st.session_state.history_records.insert(0, {
        "时间": datetime.now().strftime("%H:%M"),
        "文件名": filename,
        "AI归档分类": folder,
        "摘要预览": summary[:30] + "..." if summary else "无摘要"
    })


# ================= 2. 后台逻辑核心 (无变动) =================

class BackendLogic:
    def __init__(self, config):
        self.config = config
        os.environ["HTTP_PROXY"] = self.config["proxy_url"]
        os.environ["HTTPS_PROXY"] = self.config["proxy_url"]
        if not os.path.exists(self.config["watch_dir"]): os.makedirs(self.config["watch_dir"])
        if not os.path.exists(self.config["library_dir"]): os.makedirs(self.config["library_dir"])

    def _get_md5(self, path):
        hash_md5 = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""): hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None

    def _ai_analyze_full(self, content):
        client = OpenAI(api_key=self.config["api_key"], base_url=self.config["base_url"])
        today = datetime.now().strftime('%Y-%m-%d')
        existing = []
        if os.path.exists(self.config["library_dir"]):
            existing = [f for f in os.listdir(self.config["library_dir"]) if f.startswith(today)]

        system_prompt = "你是一个科研助理。分析文献并输出JSON。"
        user_prompt = f"""
        任务：1.决定归档文件夹名(属于{existing}则复用，否则生成'{today}'+'15字主题')。2.生成200字摘要。
        内容: {content}
        返回JSON: {{"folder_name": "...", "summary": "..."}}
        """
        try:
            resp = client.chat.completions.create(
                model=self.config["model_name"],
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            result = json.loads(resp.choices[0].message.content)
            f_name = re.sub(r'[\\/:*?"<>|]', '', result.get("folder_name", f"{today}_未分类"))
            return f_name, result.get("summary", "")
        except Exception as e:
            add_log(f"AI Error: {e}")
            return f"{today}_AI失败", ""

    def process_single_file(self, f_path, status_container=None):
        if not os.path.exists(f_path): return
        filename = os.path.basename(f_path)

        if status_container: status_container.write(f"📦 检测到文件: {filename}")
        add_log(f"📦 开始处理: {filename}")

        md5 = self._get_md5(f_path)
        history = {}
        if os.path.exists(HISTORY_DB):
            try:
                with open(HISTORY_DB, 'r', encoding='utf-8') as db:
                    history = json.load(db)
            except:
                pass

        target_folder, summary = "", ""
        if md5 in history:
            target_folder = history[md5]
            if status_container: status_container.info(f"⚡ 命中历史记录，跳过AI分析")
            add_log(f"⚡ 记忆命中: {target_folder}")
        else:
            if status_container: status_container.write("🧠 正在提取文本并进行AI分析...")
            import fitz
            text = ""
            try:
                with fitz.open(f_path) as doc:
                    for p in doc:
                        text += p.get_text()
                        if len(text) > 2000: break
            except:
                pass
            target_folder, summary = self._ai_analyze_full(text[:2000])
            add_log(f"🧠 AI决策: {target_folder}")
            history[md5] = target_folder
            with open(HISTORY_DB, 'w', encoding='utf-8') as db:
                json.dump(history, db, indent=2, ensure_ascii=False)

        full_target = os.path.join(self.config["library_dir"], target_folder)
        if not os.path.exists(full_target): os.makedirs(full_target)

        if summary:
            with open(os.path.join(full_target, "readme.txt"), "a", encoding="utf-8") as f:
                f.write(f"📄 {filename}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n📝 {summary}\n{'-' * 50}\n\n")

        dest = os.path.join(full_target, filename)
        if os.path.exists(dest): dest = os.path.join(full_target, f"copy_{int(time.time())}_{filename}")

        try:
            shutil.move(f_path, dest)
            add_log(f"✅ 归档成功: {target_folder}")
            add_history_record(filename, target_folder, summary)
            if status_container: status_container.success(f"归档完成！存入: {target_folder}")
        except Exception as e:
            add_log(f"❌ 移动失败: {e}")

    def monitor_process(self, stop_event):
        add_log("🟢 监控线程已启动")
        while not stop_event.is_set():
            try:
                files = [f for f in os.listdir(self.config["watch_dir"]) if f.lower().endswith('.pdf')]
                for f in files:
                    if stop_event.is_set(): break
                    self.process_single_file(os.path.join(self.config["watch_dir"], f))
                time.sleep(2)
            except:
                time.sleep(2)
        add_log("🔴 监控线程已停止")

    async def _smart_scroll(self, page, status_container=None):
        if status_container: status_container.write("📜 正在智能滚动加载长图文...")
        try:
            viewport_height = await page.evaluate("window.innerHeight")
            current_scroll = 0
            while True:
                doc_height = await page.evaluate("document.body.scrollHeight")
                current_scroll += (viewport_height - 100)
                await page.evaluate(f"window.scrollTo(0, {current_scroll})")
                await asyncio.sleep(random.uniform(1.0, 1.5))
                if current_scroll >= doc_height: break
            await page.evaluate(
                """() => { return Promise.all(Array.from(document.images).filter(img => !img.complete).map(img => new Promise(resolve => { img.onload = img.onerror = resolve; }))); }""")
        except:
            pass

    async def download_link_and_process(self, url, status_container):
        add_log(f"🌐 收到任务: {url}")
        target_file = None

        if "arxiv.org" in url or url.lower().endswith(".pdf"):
            status_container.write("⬇️ 检测到 PDF/ArXiv，开始高速下载...")
            if "/abs/" in url: url = url.replace("/abs/", "/pdf/")
            if not url.endswith(".pdf"): url += ".pdf"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            async with httpx.AsyncClient(verify=False, trust_env=True, follow_redirects=True,
                                         headers=headers) as client:
                try:
                    async with client.stream("GET", url, timeout=60.0) as response:
                        if response.status_code == 200:
                            fname = f"download_{int(time.time())}.pdf"
                            target_file = os.path.join(self.config["watch_dir"], fname)
                            with open(target_file, "wb") as f:
                                async for chunk in response.aiter_bytes(): f.write(chunk)
                            add_log("✅ 下载成功")
                        else:
                            add_log(f"❌ 下载失败: {response.status_code}")
                except Exception as e:
                    add_log(f"❌ 下载异常: {e}")
        else:
            status_container.write("📸 检测到网页，启动浏览器截图模式...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                try:
                    page = await context.new_page()
                    await page.goto(url, timeout=90000, wait_until="domcontentloaded")
                    title = await page.title()
                    safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip() or "webpage"
                    await self._smart_scroll(page, status_container)
                    fname = f"{safe_title}_{int(time.time())}.pdf"
                    target_file = os.path.join(self.config["watch_dir"], fname)
                    await page.emulate_media(media="screen")
                    await page.pdf(path=target_file, format="A4", print_background=True,
                                   margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"})
                    add_log(f"✅ 转换完成")
                except Exception as e:
                    add_log(f"❌ 网页失败: {e}")
                finally:
                    await browser.close()

        if target_file and os.path.exists(target_file):
            status_container.write("⚡ 下载完毕，开始AI归档...")
            self.process_single_file(target_file, status_container)


# ================= 3. Streamlit 前端界面 (原生清爽版) =================

st.set_page_config(
    page_title="Scholar Agent Pro",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 这里不加任何强制改色的 CSS，只保留最基础的
# 这样 Streamlit 会自动适配你的系统（白色/黑色模式）

config = load_config()

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 控制面板")
    with st.expander("🔑 API 配置", expanded=True):
        new_api_key = st.text_input("API Key", value=config["api_key"], type="password")
        new_base_url = st.text_input("Base URL", value=config["base_url"])
        new_model = st.text_input("Model", value=config["model_name"])

    with st.expander("🌐 网络 & 路径", expanded=False):
        new_proxy = st.text_input("Proxy", value=config["proxy_url"])
        watch_dir = st.text_input("Monitor", value=config["watch_dir"])
        library_dir = st.text_input("Library", value=config["library_dir"])

    # 按钮使用默认样式，不强制颜色
    if st.button("💾 保存配置", key="save_cfg", use_container_width=True):
        save_config({"api_key": new_api_key, "base_url": new_base_url, "model_name": new_model, "proxy_url": new_proxy,
                     "watch_dir": watch_dir, "library_dir": library_dir})
        st.success("配置已保存")
        time.sleep(0.5)
        st.rerun()

# --- 主标题 ---
st.title("🎓 Scholar Agent Pro")
st.caption(f"当前代理: `{config['proxy_url']}` | 存储库: `{config['library_dir']}`")

# --- 核心操作区 ---
col_input, col_monitor = st.columns([2, 1])

with col_input:
    # 使用 container 增加边框，提升层次感
    with st.container(border=True):
        st.subheader("📥 新任务")
        url_input = st.text_input("粘贴链接 (ArXiv / 公众号 / PDF):", label_visibility="collapsed",
                                  placeholder="https://...")

        if st.button("🚀 开始抓取并整理", type="primary", key="start_btn", use_container_width=True):
            if not url_input:
                st.warning("请先输入链接")
            else:
                with st.status("正在全自动处理中...", expanded=True) as status:
                    backend = BackendLogic(config)
                    asyncio.run(backend.download_link_and_process(url_input, status))
                    status.update(label="✅ 任务全部完成", state="complete", expanded=False)
                st.rerun()

with col_monitor:
    with st.container(border=True):
        st.subheader("📡 后台监控")
        if st.session_state.monitor_running:
            st.success("🟢 运行中")
            if st.button("⏹ 停止监控", key="stop_mon", use_container_width=True):
                st.session_state.stop_event.set()
                if st.session_state.thread_obj: st.session_state.thread_obj.join()
                st.session_state.monitor_running = False
                st.rerun()
        else:
            st.info("🔴 已停止")
            if st.button("▶ 启动监控", key="start_mon", use_container_width=True):
                st.session_state.stop_event.clear()
                backend = BackendLogic(config)
                t = threading.Thread(target=backend.monitor_process, args=(st.session_state.stop_event,), daemon=True)
                t.start()
                st.session_state.thread_obj = t
                st.session_state.monitor_running = True
                st.rerun()

st.divider()

# --- 历史记录与日志 ---
col_history, col_logs = st.columns([2, 1])

with col_history:
    st.subheader("🗂️ 今日归档记录")
    if st.session_state.history_records:
        df = pd.DataFrame(st.session_state.history_records)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "摘要预览": st.column_config.TextColumn("摘要预览", help="鼠标悬停查看详情", width="medium"),
                "AI归档分类": st.column_config.TextColumn("归档位置", width="medium")
            }
        )
    else:
        st.info("今日暂无归档记录")

with col_logs:
    st.subheader("📟 系统日志")
    # 使用原生的 text_area 显示日志，最安全清晰
    log_text = "\n".join(st.session_state.logs)
    st.text_area("Log Output", value=log_text, height=300, label_visibility="collapsed", disabled=True)

    if st.button("🔄 刷新日志", key="ref_log", use_container_width=True):
        st.rerun()