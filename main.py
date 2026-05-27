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
# 1. БАЗОВАЯ НАСТРОЙКА И ИНИЦИАЛИЗАЦИЯ
# ==========================================
st.set_page_config(page_title="Multi-Poster GOD MODE", layout="wide", page_icon="⚡")

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
    height=0,
    width=0
)

if not os.path.exists("uploads"):
    os.makedirs("uploads")

def get_db_connection():
    conn = sqlite3.connect("smm_panel.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY, password_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profiles (name TEXT PRIMARY KEY, tg_token TEXT, tg_chat TEXT, vk_token TEXT, vk_chat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, scheduled_time TEXT, text TEXT, platforms TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS templates (name TEXT PRIMARY KEY, content TEXT)''')
    
    # Таблицы для RSS
    c.execute('''CREATE TABLE IF NOT EXISTS rss_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rss_news (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT, summary TEXT, pub_date TEXT)''')
    
    # Базовые данные
    if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
        c.execute("INSERT INTO profiles VALUES ('Основной', '', '', '', '')")
    if c.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 0:
        c.execute("INSERT INTO templates VALUES ('IT Услуги', 'Ремонт ПК, настройка ПО.\\n#услуги')")
    if c.execute("SELECT COUNT(*) FROM rss_sources").fetchone()[0] == 0:
        # Добавляем профильные ленты по умолчанию
        c.execute("INSERT INTO rss_sources (url, name) VALUES ('https://habr.com/ru/rss/hub/sys_admin/all/', 'Хабр: Системное администрирование')")
        c.execute("INSERT INTO rss_sources (url, name) VALUES ('https://habr.com/ru/rss/hub/infosecurity/all/', 'Хабр: Информационная безопасность')")
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. ФОНОВЫЕ ЗАДАЧИ (RSS и Отправка)
# ==========================================
def fetch_rss_news():
    """Фоновая задача для сбора новостей"""
    conn = get_db_connection()
    sources = conn.execute("SELECT * FROM rss_sources").fetchall()
    
    for source in sources:
        try:
            feed = feedparser.parse(source['url'])
            # Берем 5 самых свежих новостей из каждой ленты
            for entry in feed.entries[:5]:
                # Проверяем, нет ли уже такой новости в базе
                exists = conn.execute("SELECT COUNT(*) FROM rss_news WHERE link=?", (entry.link,)).fetchone()[0]
                if exists == 0:
                    clean_summary = re.sub(r'<[^>]+>', '', entry.summary)[:300] + "..." # Очистка от HTML
                    conn.execute("INSERT INTO rss_news (title, link, summary, pub_date) VALUES (?, ?, ?, ?)", 
                                 (entry.title, entry.link, clean_summary, entry.published))
        except Exception as e:
            print(f"Ошибка парсинга RSS {source['url']}: {e}")
            
    conn.commit()
    conn.close()

def execute_post(text, media_paths, profile_data, tg_opts, vk_opts, post_id):
    """Фоновая задача отправки постов"""
    success_platforms = []
    tg_token, tg_chat = profile_data['tg_token'], profile_data['tg_chat']
    vk_token, vk_chat = profile_data['vk_token'], profile_data['vk_chat']
    
    # TELEGRAM
    if tg_token and tg_chat:
        try:
            bot = telebot.TeleBot(tg_token)
            pm = None if tg_opts['parse_mode'] == "Отключено" else tg_opts['parse_mode']
            if not media_paths:
                bot.send_message(tg_chat, text, parse_mode=pm, disable_notification=tg_opts['silent'], protect_content=tg_opts['protect'], disable_web_page_preview=tg_opts['no_preview'])
            elif len(media_paths) == 1:
                with open(media_paths[0], 'rb') as f:
                    bot.send_photo(tg_chat, f, caption=text[:1024], parse_mode=pm, disable_notification=tg_opts['silent'], protect_content=tg_opts['protect'])
            else:
                media = [InputMediaPhoto(open(p, 'rb').read(), caption=(text[:1024] if i==0 else None), parse_mode=pm) for i, p in enumerate(media_paths)]
                bot.send_media_group(tg_chat, media, disable_notification=tg_opts['silent'], protect_content=tg_opts['protect'])
            success_platforms.append("TG")
        except Exception as e:
            print(f"Ошибка TG: {e}")

    # VKONTAKTE
    if vk_token and vk_chat:
        try:
            vk_session = vk_api.VkApi(token=vk_token)
            vk = vk_session.get_api()
            upload = vk_api.VkUpload(vk_session)
            attachments = [f"photo{upload.photo_wall(photos=p)[0]['owner_id']}_{upload.photo_wall(photos=p)[0]['id']}" for p in media_paths] if media_paths else []
            vk.wall.post(owner_id=-int(vk_chat), message=text, attachments=",".join(attachments), from_group=1 if vk_opts['from_group'] else 0, close_comments=1 if vk_opts['close_comments'] else 0)
            success_platforms.append("VK")
        except Exception as e:
            print(f"Ошибка VK: {e}")

    conn = get_db_connection()
    status = "✅ Опубликовано: " + "+".join(success_platforms) if success_platforms else "❌ Ошибка отправки"
    conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()

    for path in media_paths:
        if os.path.exists(path):
            os.remove(path)

@st.cache_resource
def init_scheduler():
    scheduler = BackgroundScheduler()
    # Добавляем задачу на парсинг RSS каждые 4 часа
    scheduler.add_job(fetch_rss_news, 'interval', hours=4, id='rss_parser', replace_existing=True)
    scheduler.start()
    return scheduler

scheduler = init_scheduler()

if 'draft' not in st.session_state:
    st.session_state.draft = ""

# ==========================================
# 3. СИСТЕМА АВТОРИЗАЦИИ (ВХОД)
# ==========================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

conn = get_db_connection()
admin_row = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
conn.close()

if not st.session_state.authenticated:
    st.title("🔒 Панель управления")
    if not admin_row:
        st.info("Задайте Мастер-пароль для защиты панели.")
        new_pass = st.text_input("Придумайте пароль", type="password")
        if st.button("Сохранить и войти") and new_pass:
            conn = get_db_connection()
            conn.execute("INSERT INTO admin (id, password_hash) VALUES (1, ?)", (hash_password(new_pass),))
            conn.commit()
            conn.close()
            st.session_state.authenticated = True
            st.rerun()
    else:
        pwd_input = st.text_input("Введите Мастер-пароль", type="password")
        if st.button("Войти"):
            if hash_password(pwd_input) == admin_row['password_hash']:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Неверный пароль!")
    st.stop()

# ==========================================
# 4. ПОЛЬЗОВАТЕЛЬСКИЙ ИНТЕРФЕЙС
# ==========================================
st.title("⚡ Multi-Poster GOD MODE")

conn = get_db_connection()

with st.sidebar:
    if st.button("🚪 Выйти из панели"):
        st.session_state.authenticated = False
        st.rerun()
        
    st.divider()
    st.header("🗂 Профили API")
    profiles_list = [dict(row) for row in conn.execute("SELECT * FROM profiles").fetchall()]
    profile_names = [p['name'] for p in profiles_list]
    selected_profile_name = st.selectbox("Активный профиль:", profile_names)
    active_profile = next(p for p in profiles_list if p['name'] == selected_profile_name)
    
    tg_token = st.text_input("TG Token", value=active_profile["tg_token"], type="password")
    tg_chat = st.text_input("TG Chat ID", value=active_profile["tg_chat"])
    vk_token = st.text_input("VK Token", value=active_profile["vk_token"], type="password")
    vk_chat = st.text_input("VK Group ID", value=active_profile["vk_chat"])
    
    if st.button("💾 Обновить профиль"):
        conn.execute("UPDATE profiles SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? WHERE name=?", 
                     (tg_token, tg_chat, vk_token, vk_chat, selected_profile_name))
        conn.commit()
        st.success("Сохранено!")

    st.divider()
    st.header("⚙️ Telegram Опции")
    tg_pm = st.selectbox("Форматирование", ["Markdown", "HTML", "Отключено"])
    tg_sil = st.checkbox("Тихое сообщение (без звука)")
    tg_prot = st.checkbox("Защита от пересылки")
    tg_noprev = st.checkbox("Отключить превью ссылок")
    
    st.divider()
    st.header("⚙️ ВКонтакте Опции")
    vk_fg = st.checkbox("Пост от имени группы", value=True)
    vk_cc = st.checkbox("Закрыть комментарии")

# РАБОЧИЕ ВКЛАДКИ
tab_editor, tab_rss, tab_seo, tab_templates, tab_queue, tab_history = st.tabs([
    "🚀 Редактор", "📡 RSS-Лента", "🛠 SEO & UTM", "📁 Шаблоны", "⏳ Очередь", "📊 Логи"
])

# --- ВКЛАДКА: РЕДАКТОР ---
with tab_editor:
    col1, col2 = st.columns([2, 1])
    with col1:
        post_text = st.text_area("Текст сообщения", value=st.session_state.draft, height=200)
        st.session_state.draft = post_text 
        hashtags = st.text_input("Хэштеги (через пробел)")
        uploaded_files = st.file_uploader("Изображения (Мультизагрузка)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
    with col2:
        st.subheader("Настройки времени")
        is_scheduled = st.checkbox("Отложенный пост")
        if is_scheduled:
            s_date = st.date_input("Дата")
            s_time = st.time_input("Время")
            run_datetime = datetime.combine(s_date, s_time)
            st.info(f"Старт: {run_datetime.strftime('%d.%m.%Y %H:%M')}")
        else:
            run_datetime = datetime.now()
            st.info("Публикация: Мгновенно")

        submit_btn = st.button("🔥 ОТПРАВИТЬ", use_container_width=True, type="primary")

# --- ВКЛАДКА: RSS ЛЕНТА ---
with tab_rss:
    st.subheader("Новости отрасли (Автосбор)")
    
    if st.button("🔄 Принудительно собрать свежие новости"):
        with st.spinner("Опрашиваем RSS-источники..."):
            fetch_rss_news()
        st.success("Лента обновлена!")
        st.rerun()
        
    news_items = conn.execute("SELECT * FROM rss_news ORDER BY id DESC LIMIT 15").fetchall()
    
    if not news_items:
        st.info("Новостей пока нет. Нажми кнопку обновления.")
    else:
        for item in news_items:
            with st.container(border=True):
                st.markdown(f"**{item['title']}**")
                st.caption(f"Дата: {item['pub_date']}")
                st.write(item['summary'])
                
                c_btn1, c_btn2 = st.columns([1, 4])
                with c_btn1:
                    if st.button("📝 В черновик", key=f"use_{item['id']}"):
                        # Формируем готовый пост и кидаем в редактор
                        st.session_state.draft = f"📌 {item['title']}\n\nПодробности по ссылке:\n{item['link']}\n\n#новости"
                        # Удаляем новость из ленты
                        conn.execute("DELETE FROM rss_news WHERE id=?", (item['id'],))
                        conn.commit()
                        st.rerun()
                with c_btn2:
                    st.markdown(f"[Читать полный текст]({item['link']})")

# --- ВКЛАДКА: SEO & UTM ---
with tab_seo:
    st.subheader("Генератор UTM")
    utm_url = st.text_input("Ссылка (URL)")
    c1, c2, c3 = st.columns(3)
    with c1: utm_s = st.text_input("Source", placeholder="vk")
    with c2: utm_m = st.text_input("Medium", placeholder="social")
    with c3: utm_c = st.text_input("Campaign")
    if utm_url and utm_s:
        st.code(f"{utm_url}?utm_source={utm_s}&utm_medium={utm_m}&utm_campaign={utm_c}", language="text")

# --- ВКЛАДКА: ШАБЛОНЫ ---
with tab_templates:
    db_templates = [dict(row) for row in conn.execute("SELECT * FROM templates").fetchall()]
    cols = st.columns(3)
    for i, tpl in enumerate(db_templates):
        with cols[i % 3]:
            st.info(f"**{tpl['name']}**")
            if st.button("Загрузить", key=f"btn_{tpl['name']}"):
                st.session_state.draft = tpl['content']
                st.rerun()

# --- ВКЛАДКА: ОЧЕРЕДЬ ---
with tab_queue:
    st.subheader("Активные задачи в фоне")
    jobs = scheduler.get_jobs()
    for job in jobs:
        st.info(f"⏰ Запуск: {job.next_run_time.strftime('%d.%m.%Y %H:%M:%S')} | ID: {job.id}")

# --- ВКЛАДКА: ЛОГИ ---
with tab_history:
    df = pd.read_sql_query("SELECT * FROM posts ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================
# 5. ЛОГИКА ОТПРАВКИ
# ==========================================
final_text = post_text
if hashtags:
    final_text += f"\n\n{hashtags}"

if submit_btn:
    if not final_text.strip() and not uploaded_files:
        st.error("Пост пуст!")
    else:
        saved_media = []
        if uploaded_files:
            for file in uploaded_files:
                f_path = os.path.join("uploads", f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}")
                with open(f_path, "wb") as f:
                    f.write(file.getvalue())
                saved_media.append(f_path)

        profile_dict = {"tg_token": tg_token, "tg_chat": tg_chat, "vk_token": vk_token, "vk_chat": vk_chat}
        tg_options = {"parse_mode": tg_pm, "silent": tg_sil, "protect": tg_prot, "no_preview": tg_noprev}
        vk_options = {"from_group": vk_fg, "close_comments": vk_cc}
        
        status = "⏳ В очереди" if is_scheduled else "🔄 Обработка"
        c = conn.cursor()
        c.execute("INSERT INTO posts (scheduled_time, text, platforms, status) VALUES (?, ?, ?, ?)",
                  (run_datetime.strftime("%Y-%m-%d %H:%M:%S"), final_text[:50]+"...", "TG+VK", status))
        post_id = c.lastrowid
        conn.commit()

        scheduler.add_job(
            execute_post,
            trigger='date',
            run_date=run_datetime,
            args=[final_text, saved_media, profile_dict, tg_options, vk_options, post_id]
        )

        if is_scheduled:
            st.success(f"✅ Задача добавлена в расписание на {run_datetime.strftime('%d.%m.%Y %H:%M')}")
        else:
            st.success("✅ Задача ушла в фон! Статус обновится во вкладке 'Логи'.")

conn.close()
