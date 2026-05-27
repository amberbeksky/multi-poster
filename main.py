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
    height=0, 
    width=0
)

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
    c.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, scheduled_time TEXT, text TEXT, platforms TEXT, status TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS templates (name TEXT PRIMARY KEY, content TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS rss_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS rss_news (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT, summary TEXT, pub_date TEXT)')
    
    if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
        c.execute("INSERT INTO profiles VALUES ('Основной', '', '', '', '')")
        
    if c.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 0:
        c.execute("INSERT INTO templates VALUES ('IT Услуги COMPASTERVRN', 'Ремонт ПК, сборка и обслуживание.\\nНастройка ViPNet, КриптоПро и ЭЦП под ключ.\\n\\n#COMPASTERVRN #ремонтпк')")
        c.execute("INSERT INTO templates VALUES ('Уведомление', 'Внимание! Расчетные листки за текущий месяц сформированы.')")
        
    if c.execute("SELECT COUNT(*) FROM rss_sources").fetchone()[0] == 0:
        c.execute("INSERT INTO rss_sources (url, name) VALUES ('https://habr.com/ru/rss/hub/sys_admin/all/', 'Хабр: Системное администрирование')")
        c.execute("INSERT INTO rss_sources (url, name) VALUES ('https://habr.com/ru/rss/hub/infosecurity/all/', 'Хабр: Информационная безопасность')")
        
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
                    clean_summary = re.sub(r'<[^>]+>', '', entry.summary)[:250] + "..."
                    conn.execute("INSERT INTO rss_news (title, link, summary, pub_date) VALUES (?, ?, ?, ?)", 
                                 (entry.title, entry.link, clean_summary, entry.published))
        except Exception as e:
            print(f"Ошибка парсинга RSS {source['url']}: {e}")
            
    conn.commit()
    conn.close()

def execute_post(text, media_paths, profile_data, tg_opts, vk_opts, post_id):
    success_platforms = []
    
    tg_token = profile_data['tg_token']
    tg_chat = profile_data['tg_chat']
    vk_token = profile_data['vk_token']
    vk_chat = profile_data['vk_chat']
    
    # --- TELEGRAM ---
    if tg_token and tg_chat:
        try:
            bot = telebot.TeleBot(tg_token)
            pm = None if tg_opts['parse_mode'] == "Отключено" else tg_opts['parse_mode']
            
            if not media_paths:
                bot.send_message(
                    tg_chat, 
                    text, 
                    parse_mode=pm, 
                    disable_notification=tg_opts['silent'], 
                    protect_content=tg_opts['protect'], 
                    disable_web_page_preview=tg_opts['no_preview']
                )
            elif len(media_paths) == 1:
                with open(media_paths[0], 'rb') as f:
                    bot.send_photo(
                        tg_chat, 
                        f, 
                        caption=text[:1024], 
                        parse_mode=pm, 
                        disable_notification=tg_opts['silent'], 
                        protect_content=tg_opts['protect']
                    )
            else:
                media = []
                for i, path in enumerate(media_paths):
                    with open(path, 'rb') as f:
                        file_data = f.read()
                        caption = text[:1024] if i == 0 else None
                        media.append(InputMediaPhoto(file_data, caption=caption, parse_mode=pm))
                        
                bot.send_media_group(
                    tg_chat, 
                    media, 
                    disable_notification=tg_opts['silent'], 
                    protect_content=tg_opts['protect']
                )
                
            success_platforms.append("TG")
        except Exception as e:
            print(f"Ошибка TG: {e}")

    # --- VKONTAKTE ---
    if vk_token and vk_chat:
        try:
            vk_session = vk_api.VkApi(token=vk_token)
            vk = vk_session.get_api()
            upload = vk_api.VkUpload(vk_session)
            attachments = []
            
            if media_paths:
                for path in media_paths:
                    photo = upload.photo_wall(photos=path)[0]
                    attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
                    
            vk.wall.post(
                owner_id=-int(vk_chat), 
                message=text, 
                attachments=",".join(attachments) if attachments else "", 
                from_group=1 if vk_opts['from_group'] else 0, 
                close_comments=1 if vk_opts['close_comments'] else 0
            )
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
    scheduler.add_job(fetch_rss_news, 'interval', hours=4, id='rss_parser', replace_existing=True)
    scheduler.start()
    return scheduler

scheduler = init_scheduler()

# ==========================================
# 3. СИСТЕМА АВТОРИЗАЦИИ (ВХОД)
# ==========================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    
if 'draft' not in st.session_state:
    st.session_state.draft = ""

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

conn = get_db_connection()
admin_row = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
conn.close()

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: #7c3aed;'>⚡ MULTI-POSTER PRO</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not admin_row:
            st.info("Инициализация защиты. Задайте Мастер-пароль.")
            new_pass = st.text_input("Придумайте пароль", type="password")
            
            if st.button("СОХРАНИТЬ И ВОЙТИ", use_container_width=True) and new_pass:
                conn = get_db_connection()
                conn.execute("INSERT INTO admin (id, password_hash) VALUES (1, ?)", (hash_password(new_pass),))
                conn.commit()
                conn.close()
                st.session_state.authenticated = True
                st.rerun()
        else:
            st.markdown("<div style='background: rgba(30,41,59,0.5); padding: 2rem; border-radius: 12px; text-align: center;'>", unsafe_allow_html=True)
            st.write("Введите Мастер-пароль для доступа.")
            pwd_input = st.text_input("Пароль", type="password", label_visibility="collapsed")
            
            if st.button("ВХОД В СИСТЕМУ", use_container_width=True):
                if hash_password(pwd_input) == admin_row['password_hash']:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Доступ запрещен!")
            st.markdown("</div>", unsafe_allow_html=True)
            
    st.stop()

# ==========================================
# 4. ПОЛЬЗОВАТЕЛЬСКИЙ ИНТЕРФЕЙС
# ==========================================
st.markdown("<h1>⚡ Multi-Poster <span style='color: #db2777;'>GOD MODE</span></h1>", unsafe_allow_html=True)

conn = get_db_connection()

with st.sidebar:
    if st.button("🚪 ВЫЙТИ ИЗ СИСТЕМЫ", use_container_width=True):
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
    
    if st.button("💾 ОБНОВИТЬ ПРОФИЛЬ", use_container_width=True):
        conn.execute("UPDATE profiles SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? WHERE name=?", 
                     (tg_token, tg_chat, vk_token, vk_chat, selected_profile_name))
        conn.commit()
        st.success("Профиль успешно сохранен!")
        
    new_profile = st.text_input("Новый профиль (название)")
    if st.button("➕ Создать профиль") and new_profile:
        try:
            conn.execute("INSERT INTO profiles (name, tg_token, tg_chat, vk_token, vk_chat) VALUES (?, '', '', '', '')", (new_profile,))
            conn.commit()
            st.rerun()
        except:
            st.error("Профиль уже существует")

    st.divider()
    
    st.header("⚙️ Опции Telegram")
    tg_pm = st.selectbox("Форматирование", ["Markdown", "HTML", "Отключено"])
    tg_sil = st.checkbox("Тихое сообщение (без звука)")
    tg_prot = st.checkbox("Защита от пересылки")
    tg_noprev = st.checkbox("Отключить превью ссылок")
    
    st.divider()
    
    st.header("⚙️ Опции ВКонтакте")
    vk_fg = st.checkbox("Пост от имени группы", value=True)
    vk_cc = st.checkbox("Закрыть комментарии")
    
    st.divider()
    st.caption("Панель управления SMM")

# РАБОЧИЕ ВКЛАДКИ
tab_editor, tab_rss, tab_seo, tab_templates, tab_queue, tab_history = st.tabs([
    "🚀 РЕДАКТОР", "📡 RSS-ЛЕНТА", "🛠 SEO & UTM", "📁 ШАБЛОНЫ", "⏳ ОЧЕРЕДЬ", "📊 ЛОГИ"
])

# --- ВКЛАДКА: РЕДАКТОР ---
with tab_editor:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        post_text = st.text_area("Текст сообщения", value=st.session_state.draft, height=250)
        st.session_state.draft = post_text 
        
        hashtags = st.text_input("Хэштеги (через пробел)")
        uploaded_files = st.file_uploader("Изображения (Мультизагрузка)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
    with col2:
        st.markdown("### Настройки времени")
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
        
        st.markdown("### Лимиты Telegram")
        full_len = len(post_text + hashtags)
        if uploaded_files and full_len > 1024:
            st.error(f"⚠️ Текст с фото ({full_len}/1024) будет обрезан.")
        elif not uploaded_files and full_len > 4096:
            st.error(f"⚠️ Текст ({full_len}/4096) превышает лимит.")
        else:
            st.success(f"✅ Длина в норме ({full_len})")

# --- ВКЛАДКА: RSS ЛЕНТА ---
with tab_rss:
    c1, c2 = st.columns([4, 1])
    c1.markdown("### Автосбор инфоповодов")
    if c2.button("🔄 Обновить ленту", use_container_width=True):
        with st.spinner("Опрашиваем RSS-источники..."):
            fetch_rss_news()
        st.rerun()
        
    news_items = conn.execute("SELECT * FROM rss_news ORDER BY id DESC LIMIT 15").fetchall()
    
    if not news_items:
        st.info("Новостей пока нет. Нажми кнопку обновления.")
    else:
        for item in news_items:
            with st.container():
                st.markdown(f"<div class='rss-card'>", unsafe_allow_html=True)
                st.markdown(f"**{item['title']}**")
                st.caption(f"Дата: {item['pub_date']}")
                st.write(item['summary'])
                
                c_btn1, c_btn2 = st.columns([1, 4])
                with c_btn1:
                    if st.button("В черновик", key=f"use_{item['id']}"):
                        st.session_state.draft = f"📌 {item['title']}\n\nПодробности по ссылке:\n{item['link']}\n\n#новости"
                        conn.execute("DELETE FROM rss_news WHERE id=?", (item['id'],))
                        conn.commit()
                        st.rerun()
                with c_btn2:
                    st.markdown(f"[🔗 Читать полную статью]({item['link']})")
                st.markdown("</div>", unsafe_allow_html=True)

# --- ВКЛАДКА: SEO & UTM ---
with tab_seo:
    st.markdown("### Генератор UTM-меток")
    utm_url = st.text_input("Ссылка (URL)")
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        utm_s = st.text_input("Source (источник)", placeholder="vk")
    with c2: 
        utm_m = st.text_input("Medium (тип трафика)", placeholder="social")
    with c3: 
        utm_c = st.text_input("Campaign (кампания)")
        
    if utm_url and utm_s:
        st.code(f"{utm_url}?utm_source={utm_s}&utm_medium={utm_m}&utm_campaign={utm_c}", language="text")

# --- ВКЛАДКА: ШАБЛОНЫ ---
with tab_templates:
    db_templates = [dict(row) for row in conn.execute("SELECT * FROM templates").fetchall()]
    cols = st.columns(3)
    
    for i, tpl in enumerate(db_templates):
        with cols[i % 3]:
            st.info(f"**{tpl['name']}**")
            if st.button("Загрузить шаблон", key=f"btn_{tpl['name']}"):
                st.session_state.draft = tpl['content']
                st.rerun()
                
    st.divider()
    st.markdown("### Создать новый шаблон")
    new_tpl_name = st.text_input("Название шаблона")
    new_tpl_text = st.text_area("Текст шаблона")
    if st.button("Сохранить новый шаблон"):
        conn.execute("INSERT OR REPLACE INTO templates (name, content) VALUES (?, ?)", (new_tpl_name, new_tpl_text))
        conn.commit()
        st.success("Шаблон сохранен!")
        st.rerun()

# --- ВКЛАДКА: ОЧЕРЕДЬ ---
with tab_queue:
    st.markdown("### Задачи в фоновом режиме")
    jobs = scheduler.get_jobs()
    if not jobs:
        st.info("Очередь пуста. Нет запланированных публикаций.")
    for job in jobs:
        st.success(f"⏰ Запуск: {job.next_run_time.strftime('%d.%m.%Y %H:%M:%S')} | ID: {job.id}")

# --- ВКЛАДКА: ЛОГИ ---
with tab_history:
    st.markdown("### История публикаций")
    if st.button("🔄 Обновить таблицу логов"):
        st.rerun()
    df = pd.read_sql_query("SELECT * FROM posts ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================
# 5. ЛОГИКА ОТПРАВКИ ПОСТОВ
# ==========================================
final_text = post_text
if hashtags:
    final_text += f"\n\n{hashtags}"

if submit_btn:
    if not final_text.strip() and not uploaded_files:
        st.error("❌ Ошибка: Пост пуст. Добавьте текст или изображение!")
    else:
        saved_media = []
        if uploaded_files:
            for file in uploaded_files:
                f_path = os.path.join("uploads", f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}")
                with open(f_path, "wb") as f:
                    f.write(file.getvalue())
                saved_media.append(f_path)

        profile_dict = {
            "tg_token": tg_token, 
            "tg_chat": tg_chat, 
            "vk_token": vk_token, 
            "vk_chat": vk_chat
        }
        
        tg_options = {
            "parse_mode": tg_pm, 
            "silent": tg_sil, 
            "protect": tg_prot, 
            "no_preview": tg_noprev
        }
        
        vk_options = {
            "from_group": vk_fg, 
            "close_comments": vk_cc
        }
        
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
            st.success(f"✅ Задача успешно добавлена в расписание на {run_datetime.strftime('%d.%m.%Y %H:%M')}")
        else:
            st.success("✅ Задача передана в фон! Статус можно проверить во вкладке 'Логи'.")

conn.close()
