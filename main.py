import streamlit as st
import streamlit.components.v1 as components
import vk_api
import telebot
from telebot.types import InputMediaPhoto
import os
import sqlite3
import pandas as pd
from datetime import datetime
import re
import hashlib
from apscheduler.schedulers.background import BackgroundScheduler
import feedparser

# ==========================================
# 1. ULTIMATE NEON DESIGN (CUSTOM CSS)
# ==========================================
st.set_page_config(page_title="Multi-Poster GOD MODE", layout="wide", page_icon="⚡")

custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

    /* Скрытие служебных элементов Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Глубокий космический фон */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #020617 100%);
        font-family: 'JetBrains Mono', monospace;
    }

    /* Контейнеры с эффектом стекла */
    div[data-testid="stVerticalBlock"] > div {
        background: rgba(30, 41, 59, 0.25) !important;
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 15px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
    }

    /* Главные неоновые кнопки */
    div.stButton > button {
        background: linear-gradient(45deg, #7c3aed, #db2777) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.7rem 2rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1.5px !important;
        transition: all 0.3s ease !important;
        width: 100%;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3) !important;
    }
    div.stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 25px rgba(219, 39, 119, 0.5) !important;
    }

    /* Поля ввода (Инпуты) - Максимальная чёткость */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: #020617 !important;
        border: 2px solid #1e293b !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        font-size: 1rem !important;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #7c3aed !important;
        box-shadow: 0 0 10px rgba(124, 58, 237, 0.4) !important;
    }

    /* Стилизация вкладок (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(30, 41, 59, 0.5);
        border-radius: 8px 8px 0 0;
        padding: 10px 25px;
        color: #94a3b8;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .stTabs [aria-selected="true"] {
        background-color: #7c3aed !important;
        color: white !important;
        border-bottom: 3px solid #db2777 !important;
    }

    /* Боковое меню */
    section[data-testid="stSidebar"] {
        background-color: #020617 !important;
        border-right: 1px solid #1e293b;
    }

    /* Карточки RSS новостей */
    .rss-card {
        background: rgba(15, 23, 42, 0.8);
        border-radius: 12px;
        border-left: 5px solid #7c3aed;
        padding: 15px;
        margin-bottom: 15px;
        border-top: 1px solid rgba(255,255,255,0.05);
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Интеграция с Telegram Web App
components.html(
    """
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.ready();
                window.Telegram.WebApp.expand();
            }
        });
    </script>
    """,
    height=0, width=0
)

# ==========================================
# 2. ЯДРО СУБД И ФОНОВЫХ ЗАДАЧ
# ==========================================
if not os.path.exists("uploads"):
    os.makedirs("uploads")

def get_db_connection():
    conn = sqlite3.connect("smm_panel.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY, password_hash TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (name TEXT PRIMARY KEY, tg_token TEXT, tg_chat TEXT, vk_token TEXT, vk_chat TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, scheduled_time TEXT, text TEXT, platforms TEXT, status TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS templates (name TEXT PRIMARY KEY, content TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS rss_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS rss_news (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT, summary TEXT, pub_date TEXT)')
    
    if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
        c.execute("INSERT INTO profiles VALUES ('Основной', '', '', '', '')")
    if c.execute("SELECT COUNT(*) FROM rss_sources").fetchone()[0] == 0:
        c.execute("INSERT INTO rss_sources (url, name) VALUES ('https://habr.com/ru/rss/hub/sys_admin/all/', 'Хабр: Администрирование')")
        c.execute("INSERT INTO rss_sources (url, name) VALUES ('https://habr.com/ru/rss/hub/infosecurity/all/', 'Хабр: ИБ')")
    conn.commit()
    conn.close()

init_db()

def fetch_rss_news():
    conn = get_db_connection()
    sources = conn.execute("SELECT * FROM rss_sources").fetchall()
    for source in sources:
        try:
            feed = feedparser.parse(source['url'])
            for entry in feed.entries[:5]:
                exists = conn.execute("SELECT COUNT(*) FROM rss_news WHERE link=?", (entry.link,)).fetchone()[0]
                if exists == 0:
                    summary = re.sub(r'<[^>]+>', '', entry.summary)[:250] + "..."
                    conn.execute("INSERT INTO rss_news (title, link, summary, pub_date) VALUES (?, ?, ?, ?)", 
                                 (entry.title, entry.link, summary, entry.published))
        except: pass
    conn.commit()
    conn.close()

def execute_post(text, media_paths, profile_data, tg_opts, vk_opts, post_id):
    success_platforms = []
    # TG
    if profile_data['tg_token'] and profile_data['tg_chat']:
        try:
            bot = telebot.TeleBot(profile_data['tg_token'])
            pm = None if tg_opts['parse_mode'] == "Отключено" else tg_opts['parse_mode']
            if not media_paths:
                bot.send_message(profile_data['tg_chat'], text, parse_mode=pm, disable_notification=tg_opts['silent'], protect_content=tg_opts['protect'], disable_web_page_preview=tg_opts['no_preview'])
            else:
                media = [InputMediaPhoto(open(p, 'rb').read(), caption=(text[:1024] if i==0 else None), parse_mode=pm) for i, p in enumerate(media_paths)]
                bot.send_media_group(profile_data['tg_chat'], media, disable_notification=tg_opts['silent'], protect_content=tg_opts['protect'])
            success_platforms.append("TG")
        except: pass
    # VK
    if profile_data['vk_token'] and profile_data['vk_chat']:
        try:
            vk_session = vk_api.VkApi(token=profile_data['vk_token'])
            vk = vk_session.get_api()
            upload = vk_api.VkUpload(vk_session)
            attachments = [f"photo{upload.photo_wall(photos=p)[0]['owner_id']}_{upload.photo_wall(photos=p)[0]['id']}" for p in media_paths] if media_paths else []
            vk.wall.post(owner_id=-int(profile_data['vk_chat']), message=text, attachments=",".join(attachments), from_group=1 if vk_opts['from_group'] else 0, close_comments=1 if vk_opts['close_comments'] else 0)
            success_platforms.append("VK")
        except: pass

    conn = get_db_connection()
    status = "✅ OK: " + "+".join(success_platforms) if success_platforms else "❌ FAIL"
    conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()
    for p in media_paths:
        if os.path.exists(p): os.remove(p)

@st.cache_resource
def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_rss_news, 'interval', hours=4)
    scheduler.start()
    return scheduler

scheduler = init_scheduler()

# ==========================================
# 3. АВТОРИЗАЦИЯ И ВХОД
# ==========================================
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'draft' not in st.session_state: st.session_state.draft = ""

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

conn = get_db_connection()
admin = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
conn.close()

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: #7c3aed;'>⚡ MULTI-POSTER PRO</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not admin:
            new_p = st.text_input("Задайте мастер-пароль", type="password")
            if st.button("СОХРАНИТЬ", use_container_width=True) and new_p:
                c = get_db_connection(); c.execute("INSERT INTO admin VALUES (1, ?)", (hash_pw(new_p),)); c.commit(); c.close()
                st.session_state.authenticated = True; st.rerun()
        else:
            in_p = st.text_input("Вход в систему", type="password")
            if st.button("ВОЙТИ", use_container_width=True):
                if hash_pw(in_p) == admin['password_hash']:
                    st.session_state.authenticated = True; st.rerun()
                else: st.error("Неверно")
    st.stop()

# ==========================================
# 4. ИНТЕРФЕЙС (GOD MODE)
# ==========================================
st.markdown("<h1>⚡ Multi-Poster <span style='color: #db2777;'>GOD MODE</span></h1>", unsafe_allow_html=True)

conn = get_db_connection()
with st.sidebar:
    if st.button("🚪 ВЫЙТИ", use_container_width=True):
        st.session_state.authenticated = False; st.rerun()
    st.divider()
    profiles = [dict(r) for r in conn.execute("SELECT * FROM profiles").fetchall()]
    active_name = st.selectbox("Профиль:", [p['name'] for p in profiles])
    active = next(p for p in profiles if p['name'] == active_name)
    
    t_t = st.text_input("TG Token", value=active['tg_token'], type="password")
    t_c = st.text_input("TG Chat ID", value=active['tg_chat'])
    v_t = st.text_input("VK Token", value=active['vk_token'], type="password")
    v_c = st.text_input("VK Group ID", value=active['vk_chat'])
    
    if st.button("💾 СОХРАНИТЬ ПРОФИЛЬ", use_container_width=True):
        conn.execute("UPDATE profiles SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? WHERE name=?", (t_t, t_c, v_t, v_c, active_name)); conn.commit(); st.success("OK")

    st.divider()
    tg_pm = st.selectbox("TG Формат", ["Markdown", "HTML", "Отключено"])
    tg_sil = st.checkbox("Без звука")
    tg_prot = st.checkbox("Защита контента")
    vk_fg = st.checkbox("От имени группы", value=True)

tab_ed, tab_news, tab_seo, tab_tm, tab_q, tab_log = st.tabs(["🚀 РЕДАКТОР", "📡 НОВОСТИ", "🛠 SEO", "📁 ШАБЛОНЫ", "⏳ ОЧЕРЕДЬ", "📊 ЛОГИ"])

with tab_ed:
    c1, c2 = st.columns([2, 1])
    with c1:
        txt = st.text_area("Текст поста", value=st.session_state.draft, height=250)
        st.session_state.draft = txt
        tags = st.text_input("Хэштеги")
        files = st.file_uploader("Медиа (Мульти)", type=['png', 'jpg'], accept_multiple_files=True)
    with c2:
        is_sched = st.checkbox("Отложенный старт")
        run_dt = datetime.combine(st.date_input("Дата"), st.time_input("Время")) if is_sched else datetime.now()
        if st.button("🔥 ОПУБЛИКОВАТЬ", use_container_width=True, type="primary"):
            paths = []
            if files:
                for f in files:
                    p = os.path.join("uploads", f"{datetime.now().strftime('%S')}_{f.name}")
                    with open(p, "wb") as out: out.write(f.getvalue())
                    paths.append(p)
            
            final_txt = txt + (f"\n\n{tags}" if tags else "")
            curr = conn.cursor(); curr.execute("INSERT INTO posts (scheduled_time, text, platforms, status) VALUES (?,?,?,?)", (run_dt.strftime("%H:%M"), final_txt[:30]+"...", "TG+VK", "⏳ Ждем")); conn.commit()
            
            scheduler.add_job(execute_post, 'date', run_date=run_dt, args=[final_txt, paths, {"tg_token":t_t, "tg_chat":t_c, "vk_token":v_t, "vk_chat":v_c}, {"parse_mode":tg_pm, "silent":tg_sil, "protect":tg_prot, "no_preview":True}, {"from_group":vk_fg, "close_comments":True}, curr.lastrowid])
            st.success("Задача принята!")

with tab_news:
    if st.button("🔄 ОБНОВИТЬ ЛЕНТУ"): fetch_rss_news(); st.rerun()
    items = conn.execute("SELECT * FROM rss_news ORDER BY id DESC LIMIT 10").fetchall()
    for i in items:
        st.markdown(f"<div class='rss-card'><b>{i['title']}</b><br><small>{i['pub_date']}</small><br>{i['summary']}</div>", unsafe_allow_html=True)
        if st.button("📝 В черновик", key=f"rss_{i['id']}"):
            st.session_state.draft = f"📌 {i['title']}\n\n{i['link']}"; st.rerun()

with tab_seo:
    url = st.text_input("Ссылка для UTM")
    if url: st.code(f"{url}?utm_source=social&utm_medium=poster", language="text")
    if txt: st.metric("Длина текста", len(txt+tags))

with tab_tm:
    name_tm = st.text_input("Название шаблона")
    cont_tm = st.text_area("Контент")
    if st.button("Сохранить шаблон"):
        conn.execute("INSERT OR REPLACE INTO templates VALUES (?,?)", (name_tm, cont_tm)); conn.commit(); st.rerun()
    tms = conn.execute("SELECT * FROM templates").fetchall()
    for t in tms:
        if st.button(f"📄 {t['name']}", use_container_width=True): st.session_state.draft = t['content']; st.rerun()

with tab_q:
    for j in scheduler.get_jobs(): st.info(f"⏰ {j.next_run_time.strftime('%H:%M:%S')} | ID: {j.id}")

with tab_log:
    st.dataframe(pd.read_sql_query("SELECT * FROM posts ORDER BY id DESC", conn), use_container_width=True)

conn.close()
