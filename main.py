import streamlit as st
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
# 1. БАЗОВАЯ НАСТРОЙКА (БЕЗ КАСТОМНОГО CSS)
# ==========================================
st.set_page_config(page_title="Poster", layout="wide")

# Убрали весь блок custom_css и st.markdown с ним

# ==========================================
# 2. БАЗА ДАННЫХ И ФОНОВЫЕ ЗАДАЧИ
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
# 3. АВТОРИЗАЦИЯ
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
    st.title("Вход в Poster")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not admin:
            new_p = st.text_input("Создайте пароль администратора", type="password")
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
# 4. ОСНОВНОЙ ИНТЕРФЕЙС
# ==========================================

st.title("Управление публикациями")

conn = get_db_connection()

# Сайдбар со стандартными контролами
with st.sidebar:
    st.header("Настройки")
    
    if st.button("Выход", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    st.write("---")
    
    profiles = [dict(r) for r in conn.execute("SELECT * FROM profiles").fetchall()]
    active_name = st.selectbox("Активный профиль", [p['name'] for p in profiles])
    active = next(p for p in profiles if p['name'] == active_name)
    
    st.subheader("ВКонтакте")
    v_t = st.text_input("Токен VK", value=active['vk_token'], type="password")
    v_c = st.text_input("ID группы (owner_id)", value=active['vk_chat'])
    
    st.subheader("Telegram")
    t_t = st.text_input("Токен бот", value=active['tg_token'], type="password")
    t_c = st.text_input("Chat ID", value=active['tg_chat'])
    
    if st.button("Сохранить профиль", use_container_width=True):
        conn.execute("UPDATE profiles SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? WHERE name=?", 
                    (t_t, t_c, v_t, v_c, active_name))
        conn.commit()
        st.success("Настройки сохранены")
    
    st.write("---")
    
    st.subheader("Опции")
    tg_pm = st.selectbox("Формат TG", ["Markdown", "HTML", "Отключено"])
    vk_fg = st.checkbox("Пост от имени группы", value=True)

# Основные вкладки без кастомных стилей
tabs = st.tabs(["Редактор", "Новости", "Шаблоны", "История"])

# Вкладка редактора
with tabs[0]:
    st.subheader("Новая публикация")
    
    # Текст поста
    text = st.text_area("Текст поста", value=st.session_state.draft, height=200, placeholder="Введите текст публикации...")
    st.session_state.draft = text
    
    # Хэштеги
    tags = st.text_input("Хэштеги", placeholder="#ремонтпк #воронеж")
    
    # Медиа
    files = st.file_uploader("Изображения", accept_multiple_files=True)
    
    # Превью медиа (стандартное Streamlit)
    if files:
        st.write("Превью изображений:")
        cols = st.columns(min(4, len(files)))
        for i, f in enumerate(files):
            with cols[i % 4]:
                st.image(f, use_container_width=True)
    
    st.write("---")
    
    # Настройки публикации
    col1, col2 = st.columns([1, 1])
    with col1:
        is_scheduled = st.checkbox("Запланировать на время")
    with col2:
        if is_scheduled:
            date = st.date_input("Дата")
            time = st.time_input("Время")
            run_dt = datetime.combine(date, time)
        else:
            run_dt = datetime.now()
    
    st.write("---")
    
    # Кнопка публикации
    if st.button("Опубликовать", type="primary", use_container_width=True):
        paths = []
        if files:
            for f in files:
                name = f"{datetime.now().strftime('%H%M%S')}_{f.name}"
                path = os.path.join("uploads", name)
                with open(path, "wb") as out:
                    out.write(f.getvalue())
                paths.append(path)
        
        final_text = text
        if tags:
            final_text = f"{text}\n\n{tags}"
        
        # Сохраняем в БД (статус "⏳ В очереди" без CSS стилей)
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
        
        st.success(f"Готово. Задача запланирована на {run_dt.strftime('%H:%M %d.%m.%Y')}")
        st.rerun()

# Вкладка новостей RSS
with tabs[1]:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Сбор новостей из источников")
    with col2:
        if st.button("Обновить RSS", use_container_width=True):
            fetch_rss_news()
            st.rerun()
    
    news = conn.execute("SELECT * FROM rss_news ORDER BY id DESC LIMIT 15").fetchall()
    
    for item in news:
        st.write(f"**{item['title']}**")
        st.write(f"*Дата: {item['pub_date']}*")
        st.write(item['summary'])
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("В редактор", key=f"use_{item['id']}", use_container_width=True):
                st.session_state.draft = f"{item['title']}\n\n{item['link']}"
                st.rerun()
        with col2:
            st.write(f"[Открыть источник]({item['link']})")
        st.write("---")

# Вкладка шаблонов
with tabs[2]:
    st.subheader("Шаблоны постов")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Создать шаблон")
        tm_name = st.text_input("Название шаблона")
        tm_content = st.text_area("Текст", height=150)
        if st.button("Сохранить шаблон", use_container_width=True):
            if tm_name and tm_content:
                conn.execute("INSERT OR REPLACE INTO templates VALUES (?,?)", (tm_name, tm_content))
                conn.commit()
                st.success("Шаблон сохранен")
                st.rerun()
    
    with col2:
        st.markdown("### Использовать шаблон")
        templates = conn.execute("SELECT * FROM templates").fetchall()
        for tm in templates:
            if st.button(tm['name'], key=f"tmpl_{tm['name']}", use_container_width=True):
                st.session_state.draft = tm['content']
                st.rerun()

# Вкладка истории (стандартная таблица DataFrame)
with tabs[3]:
    st.subheader("Последние публикации")
    posts = pd.read_sql_query("SELECT id, scheduled_time, text, status FROM posts ORDER BY id DESC LIMIT 30", conn)
    st.dataframe(posts, use_container_width=True, hide_index=True)

conn.close()
