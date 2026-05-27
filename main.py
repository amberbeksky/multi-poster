import streamlit as st
import vk_api
import telebot
from telebot.types import InputMediaPhoto
import os
import sqlite3
import pandas as pd
from datetime import datetime
import re
from apscheduler.schedulers.background import BackgroundScheduler

# ==========================================
# 1. БАЗОВАЯ НАСТРОЙКА И ИНИЦИАЛИЗАЦИЯ
# ==========================================
st.set_page_config(page_title="Multi-Poster GOD MODE", layout="wide", page_icon="⚡")

# Создаем папку для файлов
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# Подключение к БД
def get_db_connection():
    conn = sqlite3.connect("smm_panel.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация таблиц
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS profiles 
                 (name TEXT PRIMARY KEY, tg_token TEXT, tg_chat TEXT, vk_token TEXT, vk_chat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, scheduled_time TEXT, text TEXT, platforms TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS templates 
                 (name TEXT PRIMARY KEY, content TEXT)''')
    
    # Базовый профиль
    c.execute("SELECT COUNT(*) FROM profiles")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO profiles VALUES ('Основной', '', '', '', '')")
    
    # Базовые шаблоны
    c.execute("SELECT COUNT(*) FROM templates")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO templates VALUES ('IT Услуги', 'Ремонт ПК, настройка ПО.\\n#услуги')")
    
    conn.commit()
    conn.close()

init_db()

# Запуск фонового планировщика
@st.cache_resource
def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.start()
    return scheduler

scheduler = init_scheduler()

# Черновик в сессии
if 'draft' not in st.session_state:
    st.session_state.draft = ""

# ==========================================
# 2. ФОНОВЫЙ ДВИЖОК ОТПРАВКИ
# ==========================================
def execute_post(text, media_paths, profile_data, tg_opts, vk_opts, post_id):
    success_platforms = []
    
    tg_token, tg_chat = profile_data['tg_token'], profile_data['tg_chat']
    vk_token, vk_chat = profile_data['vk_token'], profile_data['vk_chat']
    
    # TELEGRAM
    if tg_token and tg_chat:
        try:
            bot = telebot.TeleBot(tg_token)
            pm = None if tg_opts['parse_mode'] == "Отключено" else tg_opts['parse_mode']
            
            if not media_paths:
                bot.send_message(
                    tg_chat, text, parse_mode=pm, 
                    disable_notification=tg_opts['silent'], 
                    protect_content=tg_opts['protect'],
                    disable_web_page_preview=tg_opts['no_preview']
                )
            elif len(media_paths) == 1:
                with open(media_paths[0], 'rb') as f:
                    bot.send_photo(
                        tg_chat, f, caption=text[:1024], parse_mode=pm,
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

    # Обновление БД
    conn = get_db_connection()
    status = "✅ Опубликовано: " + "+".join(success_platforms) if success_platforms else "❌ Ошибка отправки"
    conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()

    # Удаление временных файлов
    for path in media_paths:
        if os.path.exists(path):
            os.remove(path)

# ==========================================
# 3. ПОЛЬЗОВАТЕЛЬСКИЙ ИНТЕРФЕЙС
# ==========================================
st.title("⚡ Multi-Poster GOD MODE")
st.write("SQLite, Фоновый постинг, Мультиаккаунты, SEO-анализ и UTM.")

conn = get_db_connection()

# БОКОВАЯ ПАНЕЛЬ (Профили и Настройки)
with st.sidebar:
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
        
    new_profile = st.text_input("Новый профиль (название)")
    if st.button("➕ Создать профиль") and new_profile:
        try:
            conn.execute("INSERT INTO profiles (name, tg_token, tg_chat, vk_token, vk_chat) VALUES (?, '', '', '', '')", (new_profile,))
            conn.commit()
            st.rerun()
        except:
            st.error("Профиль уже существует")

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
tab_editor, tab_seo, tab_templates, tab_queue, tab_history = st.tabs([
    "🚀 Редактор", "🛠 SEO & UTM", "📁 Шаблоны", "⏳ Очередь", "📊 Логи"
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
        st.subheader("Монитор лимитов")
        full_len = len(post_text + hashtags)
        if uploaded_files and full_len > 1024:
            st.error(f"⚠️ Текст с фото ({full_len}/1024) превышает лимит TG! Будет обрезан.")
        elif not uploaded_files and full_len > 4096:
            st.error(f"⚠️ Текст ({full_len}/4096) превышает лимит TG.")
        else:
            st.success(f"✅ Длина в норме ({full_len} симв.)")
            
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
        
    st.divider()
    st.subheader("Анализатор текста")
    if post_text:
        words = len(post_text.split())
        tags_count = len(re.findall(r'#\w+', post_text + " " + hashtags))
        has_cta = any(w in post_text.lower() for w in ['купить', 'заказать', 'звоните', 'ссылка', 'переходи'])
        m1, m2, m3 = st.columns(3)
        m1.metric("Слов", words)
        m2.metric("Хэштегов", tags_count, delta="- Теневой бан" if tags_count > 10 else "Ок", delta_color="inverse")
        m3.metric("Призыв (CTA)", "Есть" if has_cta else "Нет")

# --- ВКЛАДКА: ШАБЛОНЫ ---
with tab_templates:
    c_new, c_list = st.columns([1, 2])
    with c_new:
        st.subheader("Новый шаблон")
        t_name = st.text_input("Название")
        t_text = st.text_area("Текст шаблона", height=150)
        if st.button("Сохранить"):
            conn.execute("INSERT OR REPLACE INTO templates (name, content) VALUES (?, ?)", (t_name, t_text))
            conn.commit()
            st.success("Сохранено!")
            st.rerun()
            
    with c_list:
        st.subheader("Ваши шаблоны")
        db_templates = [dict(row) for row in conn.execute("SELECT * FROM templates").fetchall()]
        cols = st.columns(2)
        for i, tpl in enumerate(db_templates):
            with cols[i % 2]:
                st.info(f"**{tpl['name']}**")
                st.caption(tpl['content'][:50] + "...")
                if st.button("Загрузить", key=f"btn_{tpl['name']}"):
                    st.session_state.draft = tpl['content']
                    st.rerun()

# --- ВКЛАДКА: ОЧЕРЕДЬ ---
with tab_queue:
    st.subheader("Активные задачи в фоне")
    jobs = scheduler.get_jobs()
    if not jobs:
        st.write("Очередь пуста.")
    for job in jobs:
        st.info(f"⏰ Запуск: {job.next_run_time.strftime('%d.%m.%Y %H:%M:%S')} | ID: {job.id}")

# --- ВКЛАДКА: ЛОГИ ---
with tab_history:
    st.subheader("История из БД")
    if st.button("🔄 Обновить таблицу"):
        st.rerun()
    df = pd.read_sql_query("SELECT * FROM posts ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Экспорт в CSV", data=csv, file_name="smm_full_log.csv", mime="text/csv")

# ==========================================
# 4. ЛОГИКА ОТПРАВКИ
# ==========================================
final_text = post_text
if hashtags:
    final_text += f"\n\n{hashtags}"

if submit_btn:
    if not final_text.strip() and not uploaded_files:
        st.error("Пост пуст!")
    else:
        # Сохранение файлов локально для планировщика
        saved_media = []
        if uploaded_files:
            for file in uploaded_files:
                f_path = os.path.join("uploads", f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}")
                with open(f_path, "wb") as f:
                    f.write(file.getvalue())
                saved_media.append(f_path)

        # Сборка настроек
        profile_dict = {"tg_token": tg_token, "tg_chat": tg_chat, "vk_token": vk_token, "vk_chat": vk_chat}
        tg_options = {"parse_mode": tg_pm, "silent": tg_sil, "protect": tg_prot, "no_preview": tg_noprev}
        vk_options = {"from_group": vk_fg, "close_comments": vk_cc}
        
        # Запись в БД
        status = "⏳ В очереди" if is_scheduled else "🔄 Обработка"
        c = conn.cursor()
        c.execute("INSERT INTO posts (scheduled_time, text, platforms, status) VALUES (?, ?, ?, ?)",
                  (run_datetime.strftime("%Y-%m-%d %H:%M:%S"), final_text[:50]+"...", "TG+VK", status))
        post_id = c.lastrowid
        conn.commit()

        # Отправка задачи в APScheduler
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
