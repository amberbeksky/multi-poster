import streamlit as st
import vk_api
import telebot
from telebot.types import InputMediaPhoto
import tempfile
import os
import sqlite3
import pandas as pd
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# ==========================================
# 1. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ И ПЛАНИРОВЩИКА
# ==========================================
st.set_page_config(page_title="Multi-Poster ENTERPRISE", layout="wide", page_icon="🏢")

# Создаем папку для временных файлов отложенного постинга
if not os.path.exists("uploads"):
    os.makedirs("uploads")

def get_db_connection():
    # check_same_thread=False нужен для работы SQLite в многопоточной среде Streamlit + APScheduler
    conn = sqlite3.connect("smm_panel.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Таблица профилей
    c.execute('''CREATE TABLE IF NOT EXISTS profiles 
                 (name TEXT PRIMARY KEY, tg_token TEXT, tg_chat TEXT, vk_token TEXT, vk_chat TEXT)''')
    # Таблица истории и очереди
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, scheduled_time TEXT, text TEXT, platforms TEXT, status TEXT)''')
    
    # Добавляем профиль по умолчанию, если база пуста
    c.execute("SELECT COUNT(*) FROM profiles")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO profiles VALUES ('Основной', '', '', '', '')")
    conn.commit()
    conn.close()

init_db()

# Запускаем фоновый планировщик только один раз
@st.cache_resource
def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.start()
    return scheduler

scheduler = init_scheduler()

# ==========================================
# 2. ФУНКЦИЯ ПУБЛИКАЦИИ (ЯДРО)
# ==========================================
def execute_post(text, media_paths, tg_token, tg_chat, vk_token, vk_chat, post_id):
    success_platforms = []
    
    # --- TELEGRAM ---
    if tg_token and tg_chat:
        try:
            bot = telebot.TeleBot(tg_token)
            if not media_paths:
                bot.send_message(tg_chat, text)
            elif len(media_paths) == 1:
                with open(media_paths[0], 'rb') as f:
                    bot.send_photo(tg_chat, f, caption=text[:1024])
            else:
                media = []
                for i, path in enumerate(media_paths):
                    with open(path, 'rb') as f:
                        file_data = f.read() # Читаем в память
                        caption = text[:1024] if i == 0 else None
                        media.append(InputMediaPhoto(file_data, caption=caption))
                bot.send_media_group(tg_chat, media)
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
                from_group=1
            )
            success_platforms.append("VK")
        except Exception as e:
            print(f"Ошибка VK: {e}")

    # Обновляем статус в БД
    conn = get_db_connection()
    status = "✅ Опубликовано: " + "+".join(success_platforms) if success_platforms else "❌ Ошибка"
    conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()

    # Очищаем временные файлы
    for path in media_paths:
        if os.path.exists(path):
            os.remove(path)

# ==========================================
# 3. ИНТЕРФЕЙС БРАУЗЕРА
# ==========================================
st.title("🏢 Multi-Poster ENTERPRISE")
st.write("SQLite База данных + Фоновый Планировщик задач (APScheduler)")

conn = get_db_connection()
profiles = [dict(row) for row in conn.execute("SELECT * FROM profiles").fetchall()]

with st.sidebar:
    st.header("🗂 Профили (SQLite)")
    
    profile_names = [p['name'] for p in profiles]
    selected_profile_name = st.selectbox("Активный профиль:", profile_names)
    active_profile = next(p for p in profiles if p['name'] == selected_profile_name)
    
    tg_token = st.text_input("TG Token", value=active_profile["tg_token"], type="password")
    tg_chat = st.text_input("TG Chat ID", value=active_profile["tg_chat"])
    vk_token = st.text_input("VK Token", value=active_profile["vk_token"], type="password")
    vk_chat = st.text_input("VK Group ID", value=active_profile["vk_chat"])
    
    if st.button("💾 Обновить профиль"):
        conn.execute("UPDATE profiles SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? WHERE name=?", 
                     (tg_token, tg_chat, vk_token, vk_chat, selected_profile_name))
        conn.commit()
        st.success("Сохранено в базу!")
        
    st.divider()
    new_profile = st.text_input("Новый профиль (название)")
    if st.button("➕ Создать профиль"):
        conn.execute("INSERT INTO profiles (name, tg_token, tg_chat, vk_token, vk_chat) VALUES (?, '', '', '', '')", (new_profile,))
        conn.commit()
        st.rerun()

tab_editor, tab_queue, tab_history = st.tabs(["🚀 Создать пост", "⏳ Очередь (Таймер)", "📊 База логов"])

with tab_editor:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        post_text = st.text_area("Текст поста", height=200)
        uploaded_files = st.file_uploader("Изображения", type=['png', 'jpg'], accept_multiple_files=True)
        
    with col2:
        st.subheader("Настройки времени")
        is_scheduled = st.checkbox("Запланировать на будущее (Отложенный пост)")
        
        if is_scheduled:
            sched_date = st.date_input("Дата публикации")
            sched_time = st.time_input("Время публикации")
            run_datetime = datetime.combine(sched_date, sched_time)
            st.info(f"Старт: {run_datetime.strftime('%d.%m.%Y %H:%M')}")
        else:
            run_datetime = datetime.now()
            st.info("Публикация: Сейчас (мгновенно)")
            
        submit_btn = st.button("🔥 ПОДТВЕРДИТЬ", use_container_width=True, type="primary")

if submit_btn:
    if not post_text and not uploaded_files:
        st.error("Пост пуст!")
    else:
        # 1. Сохраняем медиа на жесткий диск, чтобы планировщик мог их взять позже
        saved_media_paths = []
        if uploaded_files:
            for file in uploaded_files:
                file_path = os.path.join("uploads", f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}")
                with open(file_path, "wb") as f:
                    f.write(file.getvalue())
                saved_media_paths.append(file_path)

        # 2. Создаем запись в базе данных
        status = "⏳ В очереди" if is_scheduled else "🔄 Отправка..."
        c = conn.cursor()
        c.execute("INSERT INTO posts (scheduled_time, text, platforms, status) VALUES (?, ?, ?, ?)",
                  (run_datetime.strftime("%Y-%m-%d %H:%M:%S"), post_text[:50]+"...", "TG+VK", status))
        post_id = c.lastrowid
        conn.commit()

        # 3. Передаем задачу планировщику (в фоне)
        scheduler.add_job(
            execute_post,
            trigger='date',
            run_date=run_datetime,
            args=[post_text, saved_media_paths, tg_token, tg_chat, vk_token, vk_chat, post_id]
        )

        if is_scheduled:
            st.success(f"✅ Пост добавлен в очередь на {run_datetime.strftime('%d.%m.%Y в %H:%M')}")
        else:
            st.success("✅ Задача передана в обработку! Обновите вкладку логов через 5 секунд.")

with tab_queue:
    st.subheader("Ожидающие публикации (APScheduler)")
    jobs = scheduler.get_jobs()
    if not jobs:
        st.write("Очередь пуста.")
    for job in jobs:
        st.info(f"⏰ Запуск: {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')} | ID Задачи: {job.id}")

with tab_history:
    st.subheader("Логи из SQLite")
    if st.button("🔄 Обновить логи"):
        st.rerun()
        
    df = pd.read_sql_query("SELECT * FROM posts ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

conn.close()
