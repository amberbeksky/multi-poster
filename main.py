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
# 1. VK STYLE DESIGN (LIGHTNING FAST)
# ==========================================
st.set_page_config(page_title="VK Poster", layout="wide", page_icon="📱")

# Минимальный CSS в стиле ВК - только необходимое, без тяжёлых градиентов
custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Скрываем лишнее Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Базовые цвета как в ВК */
    .stApp {
        background: #edeef0;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    /* Основной контейнер */
    .main .block-container {
        padding: 1rem 2rem;
        max-width: 1200px;
    }
    
    /* Карточки постов - стиль ВК */
    div[data-testid="stVerticalBlock"] > div {
        background: #ffffff;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        border: 1px solid #e7e8ec;
    }
    
    /* Кнопки в стиле ВК */
    div.stButton > button {
        background: #5181b8 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        transition: background 0.1s ease !important;
        width: auto;
        box-shadow: none !important;
    }
    div.stButton > button:hover {
        background: #4474ab !important;
        box-shadow: none !important;
    }
    
    /* Вторичные кнопки */
    div.stButton > button:has(svg) {
        background: #f5f6f7 !important;
        color: #2c3e50 !important;
        border: 1px solid #d0d3d6 !important;
    }
    
    /* Поля ввода */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: #ffffff !important;
        border: 1px solid #d0d3d6 !important;
        color: #000000 !important;
        border-radius: 8px !important;
        font-size: 14px !important;
        padding: 10px 12px !important;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #5181b8 !important;
        outline: none;
    }
    
    /* Вкладки как в ВК */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        background: #ffffff;
        border-radius: 12px;
        padding: 4px;
        margin-bottom: 16px;
        border: 1px solid #e7e8ec;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        padding: 8px 20px;
        color: #656565;
        font-weight: 500;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background: #5181b8 !important;
        color: white !important;
    }
    
    /* Сайдбар */
    section[data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid #e7e8ec;
        padding: 20px 12px;
    }
    
    /* Аватар и статус */
    .vk-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        background: white;
        border-radius: 12px;
        margin-bottom: 20px;
        border: 1px solid #e7e8ec;
    }
    .vk-avatar {
        width: 48px;
        height: 48px;
        background: #5181b8;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 20px;
    }
    
    /* Новости RSS в стиле ВК */
    .news-item {
        background: white;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        border: 1px solid #e7e8ec;
        transition: background 0.1s;
    }
    .news-item:hover {
        background: #f5f7fa;
    }
    .news-title {
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 6px;
        color: #2c3e50;
    }
    .news-meta {
        font-size: 12px;
        color: #939393;
        margin-bottom: 8px;
    }
    .news-summary {
        font-size: 13px;
        color: #656565;
        line-height: 1.4;
    }
    
    /* Предпросмотр поста */
    .post-preview {
        background: #f5f7fa;
        border-radius: 10px;
        padding: 12px;
        font-size: 13px;
        border-left: 3px solid #5181b8;
    }
    
    /* Медиа галерея */
    .media-preview {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 10px;
    }
    .media-thumb {
        width: 80px;
        height: 80px;
        background: #e7e8ec;
        border-radius: 8px;
        object-fit: cover;
    }
    
    /* Анимации - минимальные */
    .stButton > button, .stTextInput input, .stTextArea textarea {
        transition: all 0.1s ease;
    }
    
    /* Индикаторы статуса */
    .status-ok {
        color: #4bb34b;
        font-size: 12px;
    }
    .status-wait {
        color: #f0ad4e;
        font-size: 12px;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Telegram Web App интеграция - легковесная
components.html(
    """
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
        }
    </script>
    """,
    height=0
)

# ==========================================
# 2. БАЗА ДАННЫХ - БЫСТРАЯ ИНИЦИАЛИЗАЦИЯ
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
    c.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, scheduled_time TEXT, text TEXT, platforms TEXT, status TEXT, full_text TEXT)')
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
    """Лёгкий парсинг RSS без лишних запросов"""
    conn = get_db_connection()
    sources = conn.execute("SELECT * FROM rss_sources").fetchall()
    for source in sources:
        try:
            feed = feedparser.parse(source['url'])
            for entry in feed.entries[:5]:
                exists = conn.execute("SELECT COUNT(*) FROM rss_news WHERE link=?", (entry.link,)).fetchone()[0]
                if exists == 0:
                    summary = re.sub(r'<[^>]+>', '', entry.summary)[:200] + "..."
                    conn.execute("INSERT INTO rss_news (title, link, summary, pub_date) VALUES (?, ?, ?, ?)", 
                                 (entry.title, entry.link, summary, entry.published))
        except:
            pass
    conn.commit()
    conn.close()

def execute_post(text, media_paths, profile_data, tg_opts, vk_opts, post_id):
    """Отправка поста - оптимизированная"""
    success_platforms = []
    
    # Telegram отправка
    if profile_data['tg_token'] and profile_data['tg_chat']:
        try:
            bot = telebot.TeleBot(profile_data['tg_token'])
            parse_mode = None if tg_opts['parse_mode'] == "Отключено" else tg_opts['parse_mode']
            if not media_paths:
                bot.send_message(profile_data['tg_chat'], text, parse_mode=parse_mode)
            else:
                media = []
                for i, p in enumerate(media_paths):
                    with open(p, 'rb') as f:
                        caption = text[:1024] if i == 0 else None
                        media.append(InputMediaPhoto(f.read(), caption=caption, parse_mode=parse_mode))
                bot.send_media_group(profile_data['tg_chat'], media)
            success_platforms.append("TG")
        except:
            pass
    
    # VK отправка
    if profile_data['vk_token'] and profile_data['vk_chat']:
        try:
            vk_session = vk_api.VkApi(token=profile_data['vk_token'])
            vk = vk_session.get_api()
            attachments = []
            if media_paths:
                upload = vk_api.VkUpload(vk_session)
                for p in media_paths:
                    photo = upload.photo_wall(photos=p)[0]
                    attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
            vk.wall.post(
                owner_id=-int(profile_data['vk_chat']),
                message=text,
                attachments=",".join(attachments),
                from_group=1 if vk_opts['from_group'] else 0
            )
            success_platforms.append("VK")
        except:
            pass
    
    conn = get_db_connection()
    status = "✅ Готово: " + ", ".join(success_platforms) if success_platforms else "❌ Ошибка"
    conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()
    
    for p in media_paths:
        if os.path.exists(p):
            os.remove(p)

@st.cache_resource
def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_rss_news, 'interval', hours=4)
    scheduler.start()
    return scheduler

scheduler = init_scheduler()

# ==========================================
# 3. АВТОРИЗАЦИЯ - ЛЁГКАЯ
# ==========================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'draft' not in st.session_state:
    st.session_state.draft = ""

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

conn = get_db_connection()
admin = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
conn.close()

if not st.session_state.authenticated:
    st.markdown("""
        <div style="text-align: center; padding: 40px 20px;">
            <div style="width: 80px; height: 80px; background: #5181b8; border-radius: 20px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center;">
                <span style="font-size: 36px; color: white;">📱</span>
            </div>
            <h2 style="color: #2c3e50;">VK Poster</h2>
            <p style="color: #656565;">Управление постами ВКонтакте и Telegram</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not admin:
            new_p = st.text_input("Создайте пароль", type="password")
            if st.button("Создать", use_container_width=True) and new_p:
                c = get_db_connection()
                c.execute("INSERT INTO admin VALUES (1, ?)", (hash_pw(new_p),))
                c.commit()
                c.close()
                st.session_state.authenticated = True
                st.rerun()
        else:
            in_p = st.text_input("Пароль", type="password")
            if st.button("Войти", use_container_width=True):
                if hash_pw(in_p) == admin['password_hash']:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Неверный пароль")
    st.stop()

# ==========================================
# 4. ОСНОВНОЙ ИНТЕРФЕЙС - СТИЛЬ ВК
# ==========================================

# Шапка в стиле ВК
st.markdown("""
    <div class="vk-header">
        <div class="vk-avatar">📱</div>
        <div>
            <div style="font-weight: 600;">VK Poster</div>
            <div style="font-size: 12px; color: #939393;">Multi-platform publishing</div>
        </div>
    </div>
""", unsafe_allow_html=True)

conn = get_db_connection()

# Сайдбар с настройками профилей
with st.sidebar:
    st.markdown("### ⚙️ Настройки")
    
    if st.button("🚪 Выход", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    st.divider()
    
    profiles = [dict(r) for r in conn.execute("SELECT * FROM profiles").fetchall()]
    active_name = st.selectbox("Профиль", [p['name'] for p in profiles])
    active = next(p for p in profiles if p['name'] == active_name)
    
    st.markdown("#### ВКонтакте")
    v_t = st.text_input("Токен VK", value=active['vk_token'], type="password")
    v_c = st.text_input("ID группы", value=active['vk_chat'])
    
    st.markdown("#### Telegram")
    t_t = st.text_input("Токен TG", value=active['tg_token'], type="password")
    t_c = st.text_input("Chat ID", value=active['tg_chat'])
    
    if st.button("💾 Сохранить", use_container_width=True):
        conn.execute("UPDATE profiles SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? WHERE name=?", 
                    (t_t, t_c, v_t, v_c, active_name))
        conn.commit()
        st.success("Сохранено")
    
    st.divider()
    
    st.markdown("#### Дополнительно")
    tg_pm = st.selectbox("Формат TG", ["Markdown", "HTML", "Отключено"])
    vk_fg = st.checkbox("От имени группы", value=True)

# Основные вкладки
tabs = st.tabs(["✏️ Редактор", "📰 Новости", "📁 Шаблоны", "📋 История"])

# Вкладка редактора
with tabs[0]:
    # Предпросмотр
    with st.container():
        st.markdown("#### Новый пост")
        
        # Текст поста
        text = st.text_area("Текст", value=st.session_state.draft, height=200, placeholder="Что нового?")
        st.session_state.draft = text
        
        # Хэштеги
        tags = st.text_input("Хэштеги", placeholder="#пример #пост")
        
        # Медиа
        files = st.file_uploader("Фото", type=['png', 'jpg', 'jpeg', 'gif'], accept_multiple_files=True)
        
        # Превью медиа
        if files:
            cols = st.columns(min(4, len(files)))
            for i, f in enumerate(files):
                with cols[i % 4]:
                    st.image(f, use_container_width=True)
        
        # Настройки публикации
        col1, col2 = st.columns([1, 1])
        with col1:
            is_scheduled = st.checkbox("Отложить")
        with col2:
            if is_scheduled:
                date = st.date_input("Дата")
                time = st.time_input("Время")
                run_dt = datetime.combine(date, time)
            else:
                run_dt = datetime.now()
        
        # Кнопка публикации
        if st.button("📤 Опубликовать", type="primary", use_container_width=True):
            # Сохраняем медиа
            paths = []
            if files:
                for f in files:
                    name = f"{datetime.now().strftime('%H%M%S')}_{f.name}"
                    path = os.path.join("uploads", name)
                    with open(path, "wb") as out:
                        out.write(f.getvalue())
                    paths.append(path)
            
            # Формируем текст с хэштегами
            final_text = text
            if tags:
                final_text = f"{text}\n\n{tags}"
            
            # Сохраняем в БД
            cur = conn.cursor()
            cur.execute("INSERT INTO posts (scheduled_time, text, platforms, status, full_text) VALUES (?,?,?,?,?)",
                       (run_dt.strftime("%Y-%m-%d %H:%M"), final_text[:50] + "...", "VK+TG", "⏳ В очереди", final_text))
            post_id = cur.lastrowid
            conn.commit()
            
            # Планируем задачу
            scheduler.add_job(
                execute_post, 'date', run_date=run_dt,
                args=[
                    final_text, paths,
                    {"tg_token": t_t, "tg_chat": t_c, "vk_token": v_t, "vk_chat": v_c},
                    {"parse_mode": tg_pm, "silent": False, "protect": False, "no_preview": True},
                    {"from_group": vk_fg, "close_comments": False},
                    post_id
                ]
            )
            
            st.success(f"✅ Пост запланирован на {run_dt.strftime('%H:%M %d.%m.%Y')}")
            st.rerun()

# Вкладка новостей RSS
with tabs[1]:
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Обновить", use_container_width=True):
            fetch_rss_news()
            st.rerun()
    
    news = conn.execute("SELECT * FROM rss_news ORDER BY id DESC LIMIT 15").fetchall()
    
    for item in news:
        with st.container():
            st.markdown(f"""
                <div class="news-item">
                    <div class="news-title">{item['title']}</div>
                    <div class="news-meta">{item['pub_date']}</div>
                    <div class="news-summary">{item['summary']}</div>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("📝 В пост", key=f"use_{item['id']}", use_container_width=True):
                    st.session_state.draft = f"{item['title']}\n\n{item['link']}"
                    st.rerun()
            with col2:
                if st.button("🔗 Открыть", key=f"link_{item['id']}", use_container_width=True):
                    st.markdown(f"[Читать]({item['link']})")

# Вкладка шаблонов
with tabs[2]:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Создать шаблон")
        tm_name = st.text_input("Название")
        tm_content = st.text_area("Текст шаблона", height=150)
        if st.button("💾 Сохранить шаблон", use_container_width=True):
            if tm_name and tm_content:
                conn.execute("INSERT OR REPLACE INTO templates VALUES (?,?)", (tm_name, tm_content))
                conn.commit()
                st.success("Сохранено")
                st.rerun()
    
    with col2:
        st.markdown("#### Мои шаблоны")
        templates = conn.execute("SELECT * FROM templates").fetchall()
        for tm in templates:
            if st.button(f"📄 {tm['name']}", key=f"tmpl_{tm['name']}", use_container_width=True):
                st.session_state.draft = tm['content']
                st.rerun()

# Вкладка истории
with tabs[3]:
    posts = pd.read_sql_query("SELECT id, scheduled_time, text, status FROM posts ORDER BY id DESC LIMIT 30", conn)
    if not posts.empty:
        for _, post in posts.iterrows():
            status_class = "status-ok" if "✅" in post['status'] else "status-wait"
            st.markdown(f"""
                <div style="background: white; border-radius: 10px; padding: 12px; margin-bottom: 8px; border: 1px solid #e7e8ec;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                        <span style="font-size: 12px; color: #939393;">{post['scheduled_time']}</span>
                        <span class="{status_class}" style="font-size: 11px;">{post['status']}</span>
                    </div>
                    <div style="font-size: 13px;">{post['text']}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style="text-align: center; padding: 40px; color: #939393;">
                📭 История постов пуста
            </div>
        """, unsafe_allow_html=True)

conn.close()
