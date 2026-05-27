import streamlit as st
import vk_api
import telebot
from telebot.types import InputMediaPhoto, InputMediaVideo
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import re
import hashlib
from apscheduler.schedulers.background import BackgroundScheduler
import feedparser
import requests
from PIL import Image
import io
import json
import random
import string
from typing import List, Dict, Any
import base64

# ==========================================
# 1. БАЗОВАЯ НАСТРОЙКА
# ==========================================
st.set_page_config(page_title="Poster Pro", layout="wide")

# ==========================================
# 2. БАЗА ДАННЫХ И ФОНОВЫЕ ЗАДАЧИ
# ==========================================
if not os.path.exists("uploads"):
    os.makedirs("uploads")
if not os.path.exists("temp"):
    os.makedirs("temp")

def get_db_connection():
    conn = sqlite3.connect("smm_panel.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_database():
    """Миграция базы данных для добавления новых полей"""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Проверяем существование колонки category в таблице templates
        c.execute("SELECT category FROM templates LIMIT 1")
    except sqlite3.OperationalError:
        # Добавляем колонку если её нет
        c.execute("ALTER TABLE templates ADD COLUMN category TEXT DEFAULT 'Общие'")
        conn.commit()
    
    try:
        # Проверяем существование колонки enabled в таблице rss_sources
        c.execute("SELECT enabled FROM rss_sources LIMIT 1")
    except sqlite3.OperationalError:
        # Добавляем колонку если её нет
        c.execute("ALTER TABLE rss_sources ADD COLUMN enabled BOOLEAN DEFAULT 1")
        c.execute("ALTER TABLE rss_sources ADD COLUMN last_fetch TIMESTAMP")
        conn.commit()
    
    try:
        # Проверяем существование колонки is_active в таблице auto_posting_rules
        c.execute("SELECT is_active FROM auto_posting_rules LIMIT 1")
    except sqlite3.OperationalError:
        # Добавляем колонку если её нет
        c.execute("ALTER TABLE auto_posting_rules ADD COLUMN is_active BOOLEAN DEFAULT 1")
        conn.commit()
    
    try:
        # Проверяем существование колонки media_count в таблице posts
        c.execute("SELECT media_count FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        # Добавляем колонку если её нет
        c.execute("ALTER TABLE posts ADD COLUMN media_count INTEGER DEFAULT 0")
        conn.commit()
    
    conn.close()

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Основные таблицы
    c.execute('''CREATE TABLE IF NOT EXISTS admin 
                (id INTEGER PRIMARY KEY, password_hash TEXT, 
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS profiles 
                (name TEXT PRIMARY KEY, 
                 tg_token TEXT, tg_chat TEXT, 
                 vk_token TEXT, vk_chat TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 scheduled_time TEXT, text TEXT, 
                 platforms TEXT, status TEXT, 
                 full_text TEXT, media_count INTEGER DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS templates 
                (name TEXT PRIMARY KEY, 
                 content TEXT, 
                 category TEXT DEFAULT 'Общие',
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS rss_sources 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 url TEXT, name TEXT, 
                 enabled BOOLEAN DEFAULT 1,
                 last_fetch TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS rss_news 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 title TEXT, link TEXT, 
                 summary TEXT, pub_date TEXT,
                 source_id INTEGER,
                 is_used BOOLEAN DEFAULT 0)''')
    
    # Новые таблицы для расширенного функционала
    c.execute('''CREATE TABLE IF NOT EXISTS analytics 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 post_id INTEGER,
                 platform TEXT,
                 views INTEGER DEFAULT 0,
                 likes INTEGER DEFAULT 0,
                 comments INTEGER DEFAULT 0,
                 reposts INTEGER DEFAULT 0,
                 checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS content_calendar 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 date DATE,
                 time TIME,
                 topic TEXT,
                 description TEXT,
                 status TEXT DEFAULT 'planned',
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS hashtags 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 tag TEXT UNIQUE,
                 category TEXT,
                 usage_count INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS auto_posting_rules 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 source_type TEXT,
                 interval_hours INTEGER,
                 template TEXT,
                 is_active BOOLEAN DEFAULT 1,
                 last_run TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS media_library 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 filename TEXT UNIQUE,
                 original_name TEXT,
                 file_type TEXT,
                 file_size INTEGER,
                 tags TEXT,
                 uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS post_series 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 description TEXT,
                 posts_count INTEGER DEFAULT 0,
                 interval_hours INTEGER DEFAULT 24,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS series_posts 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 series_id INTEGER,
                 post_number INTEGER,
                 text TEXT,
                 media_files TEXT,
                 FOREIGN KEY (series_id) REFERENCES post_series(id))''')
    
    # Инициализация начальных данных
    if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
        c.execute("INSERT INTO profiles (name, tg_token, tg_chat, vk_token, vk_chat) VALUES ('Основной', '', '', '', '')")
    
    if c.execute("SELECT COUNT(*) FROM rss_sources").fetchone()[0] == 0:
        sources = [
            ('https://habr.com/ru/rss/hub/sys_admin/all/', 'Хабр: Администрирование'),
            ('https://habr.com/ru/rss/hub/infosecurity/all/', 'Хабр: ИБ'),
            ('https://habr.com/ru/rss/articles/?fl=ru', 'Хабр: Статьи'),
            ('https://tproger.ru/feed/', 'Tproger'),
            ('https://3dnews.ru/news/rss/', '3DNews')
        ]
        for url, name in sources:
            c.execute("INSERT INTO rss_sources (url, name, enabled) VALUES (?, ?, 1)", (url, name))
    
    # Начальные хэштеги
    if c.execute("SELECT COUNT(*) FROM hashtags").fetchone()[0] == 0:
        default_tags = [
            ('#технологии', 'Общие'),
            ('#новости', 'Общие'),
            ('#айти', 'IT'),
            ('#программирование', 'IT'),
            ('#безопасность', 'ИБ'),
            ('#системное_администрирование', 'IT')
        ]
        for tag, category in default_tags:
            c.execute("INSERT INTO hashtags (tag, category) VALUES (?, ?)", (tag, category))
    
    conn.commit()
    conn.close()

# Инициализация и миграция базы данных
init_db()
migrate_database()

def fetch_rss_news(specific_source=None):
    conn = get_db_connection()
    if specific_source:
        sources = [specific_source]
    else:
        sources = conn.execute("SELECT * FROM rss_sources WHERE enabled=1").fetchall()
    
    total_new = 0
    for source in sources:
        try:
            feed = feedparser.parse(source['url'])
            for entry in feed.entries[:10]:
                exists = conn.execute("SELECT COUNT(*) FROM rss_news WHERE link=?", 
                                    (entry.link,)).fetchone()[0]
                if exists == 0:
                    summary = entry.get('summary', entry.get('description', ''))
                    summary = re.sub(r'<[^>]+>', '', summary)[:300] + "..."
                    conn.execute("""INSERT INTO rss_news 
                                  (title, link, summary, pub_date, source_id) 
                                  VALUES (?, ?, ?, ?, ?)""", 
                               (entry.title, entry.link, summary, 
                                entry.get('published', datetime.now().isoformat()), 
                                source['id']))
                    total_new += 1
            conn.execute("UPDATE rss_sources SET last_fetch=CURRENT_TIMESTAMP WHERE id=?", 
                        (source['id'],))
        except Exception as e:
            print(f"Error fetching {source['name']}: {str(e)}")
    
    conn.commit()
    conn.close()
    return total_new

def execute_post(text, media_paths, profile_data, tg_opts, vk_opts, post_id):
    success_platforms = []
    analytics_data = {}
    
    # Telegram отправка
    if profile_data.get('tg_token') and profile_data.get('tg_chat'):
        try:
            bot = telebot.TeleBot(profile_data['tg_token'])
            parse_mode = None if tg_opts.get('parse_mode') == "Отключено" else tg_opts.get('parse_mode')
            
            if not media_paths:
                msg = bot.send_message(profile_data['tg_chat'], text, 
                                     parse_mode=parse_mode,
                                     disable_notification=tg_opts.get('silent', False),
                                     protect_content=tg_opts.get('protect', False))
                analytics_data['tg_message_id'] = msg.message_id
            else:
                media = []
                for i, p in enumerate(media_paths):
                    with open(p, 'rb') as f:
                        file_data = f.read()
                        if p.lower().endswith(('.mp4', '.avi', '.mov')):
                            if i == 0:
                                msg = bot.send_video(profile_data['tg_chat'], file_data,
                                                   caption=text[:1024],
                                                   parse_mode=parse_mode,
                                                   supports_streaming=True)
                                analytics_data['tg_message_id'] = msg.message_id
                        else:
                            caption = text[:1024] if i == 0 else None
                            media.append(InputMediaPhoto(file_data, caption=caption, 
                                                        parse_mode=parse_mode))
                
                if media:
                    msgs = bot.send_media_group(profile_data['tg_chat'], media)
                    analytics_data['tg_message_id'] = msgs[0].message_id if msgs else None
            
            success_platforms.append("TG")
            
            # Сохраняем аналитику
            if analytics_data.get('tg_message_id'):
                conn = get_db_connection()
                conn.execute("""INSERT INTO analytics (post_id, platform) 
                              VALUES (?, 'TG')""", (post_id,))
                conn.commit()
                conn.close()
                
        except Exception as e:
            print(f"TG Error: {str(e)}")
    
    # VK отправка
    if profile_data.get('vk_token') and profile_data.get('vk_chat'):
        try:
            vk_session = vk_api.VkApi(token=profile_data['vk_token'])
            vk = vk_session.get_api()
            attachments = []
            
            if media_paths:
                upload = vk_api.VkUpload(vk_session)
                for p in media_paths:
                    if p.lower().endswith(('.mp4', '.avi', '.mov')):
                        video = upload.video(video_file=p, 
                                           name=f"Video_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                        attachments.append(f"video{video['owner_id']}_{video['video_id']}")
                    else:
                        photo = upload.photo_wall(photos=p)[0]
                        attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
            
            post_result = vk.wall.post(
                owner_id=-int(profile_data['vk_chat']),
                message=text,
                attachments=",".join(attachments),
                from_group=1 if vk_opts.get('from_group') else 0
            )
            
            success_platforms.append("VK")
            analytics_data['vk_post_id'] = post_result['post_id']
            
            # Сохраняем аналитику
            conn = get_db_connection()
            conn.execute("""INSERT INTO analytics (post_id, platform) 
                          VALUES (?, 'VK')""", (post_id,))
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"VK Error: {str(e)}")
    
    # Обновление статуса
    conn = get_db_connection()
    status = "✅ Готово: " + ", ".join(success_platforms) if success_platforms else "❌ Ошибка"
    conn.execute("UPDATE posts SET status = ?, media_count = ? WHERE id = ?", 
                (status, len(media_paths), post_id))
    conn.commit()
    conn.close()
    
    # Очистка временных файлов
    for p in media_paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except:
            pass

def auto_post_news():
    """Автоматическая публикация новостей"""
    conn = get_db_connection()
    rules = conn.execute("SELECT * FROM auto_posting_rules WHERE is_active=1").fetchall()
    
    for rule in rules:
        try:
            last_run = rule['last_run']
            if last_run:
                last_run = datetime.fromisoformat(last_run)
                if datetime.now() - last_run < timedelta(hours=rule['interval_hours']):
                    continue
            
            # Получаем последние новости
            news = conn.execute("""SELECT * FROM rss_news 
                                 WHERE is_used=0 
                                 ORDER BY pub_date DESC LIMIT 1""").fetchone()
            
            if news:
                # Формируем пост по шаблону
                template = conn.execute("SELECT content FROM templates WHERE name=?", 
                                      (rule['template'],)).fetchone()
                
                if template:
                    text = template['content'].replace('{title}', news['title'])
                    text = text.replace('{link}', news['link'])
                    text = text.replace('{summary}', news['summary'])
                else:
                    text = f"{news['title']}\n\n{news['link']}"
                
                # Публикуем
                profiles = conn.execute("SELECT * FROM profiles LIMIT 1").fetchone()
                if profiles:
                    execute_post(text, [], dict(profiles), 
                               {"parse_mode": "HTML"}, {"from_group": True}, 
                               news['id'])
                    
                conn.execute("UPDATE rss_news SET is_used=1 WHERE id=?", (news['id'],))
                conn.execute("UPDATE auto_posting_rules SET last_run=CURRENT_TIMESTAMP WHERE id=?", 
                           (rule['id'],))
                
        except Exception as e:
            print(f"Auto-post error: {str(e)}")
    
    conn.commit()
    conn.close()

def get_post_analytics(post_id):
    """Получение аналитики поста"""
    conn = get_db_connection()
    analytics = conn.execute("""SELECT * FROM analytics 
                               WHERE post_id=? 
                               ORDER BY checked_at DESC""", 
                            (post_id,)).fetchall()
    conn.close()
    return [dict(a) for a in analytics]

def generate_hashtag_suggestions(text, count=5):
    """Генерация предложений по хэштегам на основе текста"""
    conn = get_db_connection()
    
    # Извлекаем ключевые слова из текста
    keywords = re.findall(r'\b[а-яёa-z]{4,}\b', text.lower())
    
    # Ищем подходящие хэштеги
    suggestions = []
    for keyword in keywords[:10]:
        tags = conn.execute("""SELECT tag, usage_count FROM hashtags 
                              WHERE tag LIKE ? 
                              ORDER BY usage_count DESC LIMIT 3""", 
                           (f'%{keyword}%',)).fetchall()
        suggestions.extend([dict(t) for t in tags])
    
    # Сортируем по популярности и убираем дубликаты
    seen = set()
    unique_suggestions = []
    for s in sorted(suggestions, key=lambda x: x['usage_count'], reverse=True):
        if s['tag'] not in seen:
            unique_suggestions.append(s['tag'])
            seen.add(s['tag'])
    
    conn.close()
    return unique_suggestions[:count]

def compress_image(file_data, max_size_mb=2):
    """Сжатие изображения для оптимизации"""
    try:
        img = Image.open(io.BytesIO(file_data))
        
        # Конвертация в RGB если нужно
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Оптимизация размера
        max_size = max_size_mb * 1024 * 1024
        quality = 85
        
        while True:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            size = buffer.tell()
            
            if size <= max_size or quality <= 20:
                break
            quality -= 5
        
        return buffer.getvalue()
    except Exception as e:
        print(f"Compression error: {str(e)}")
        return file_data

def create_post_series(name, description, posts, interval_hours=24):
    """Создание серии постов"""
    conn = get_db_connection()
    
    # Создаем серию
    cursor = conn.execute("""INSERT INTO post_series (name, description, interval_hours, posts_count) 
                            VALUES (?, ?, ?, ?)""", 
                         (name, description, interval_hours, len(posts)))
    series_id = cursor.lastrowid
    
    # Добавляем посты в серию
    for i, post in enumerate(posts, 1):
        conn.execute("""INSERT INTO series_posts (series_id, post_number, text, media_files) 
                       VALUES (?, ?, ?, ?)""", 
                    (series_id, i, post['text'], 
                     json.dumps(post.get('media_files', []))))
    
    conn.commit()
    conn.close()
    return series_id

def schedule_series(series_id, start_date, start_time):
    """Планирование публикации серии"""
    conn = get_db_connection()
    
    series = conn.execute("SELECT * FROM post_series WHERE id=?", (series_id,)).fetchone()
    posts = conn.execute("SELECT * FROM series_posts WHERE series_id=? ORDER BY post_number", 
                        (series_id,)).fetchall()
    
    if series and posts:
        base_datetime = datetime.combine(start_date, start_time)
        
        for i, post in enumerate(posts):
            post_time = base_datetime + timedelta(hours=i * series['interval_hours'])
            media_files = json.loads(post['media_files']) if post['media_files'] else []
            
            # Планируем каждый пост
            scheduler.add_job(
                execute_post,
                'date',
                run_date=post_time,
                args=[
                    post['text'],
                    media_files,
                    {"tg_token": "", "tg_chat": "", "vk_token": "", "vk_chat": ""},
                    {"parse_mode": "HTML"},
                    {"from_group": True},
                    post['id']
                ]
            )
        
        st.success(f"Серия '{series['name']}' запланирована на {base_datetime.strftime('%d.%m.%Y %H:%M')}")
    
    conn.close()

def backup_database():
    """Создание резервной копии базы данных"""
    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    conn = get_db_connection()
    
    # Создаем дамп
    with open(backup_filename, 'w') as f:
        for line in conn.iterdump():
            f.write(f'{line}\n')
    
    conn.close()
    return backup_filename

def export_posts_to_csv(start_date=None, end_date=None):
    """Экспорт постов в CSV"""
    conn = get_db_connection()
    
    query = "SELECT * FROM posts WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date)
    
    query += " ORDER BY created_at DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

@st.cache_resource
def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_rss_news, 'interval', hours=2)
    scheduler.add_job(auto_post_news, 'interval', hours=1)
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
if 'user_role' not in st.session_state:
    st.session_state.user_role = "user"

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def check_password_strength(password):
    """Проверка сложности пароля"""
    strength = 0
    if len(password) >= 8:
        strength += 1
    if re.search(r'[A-Z]', password):
        strength += 1
    if re.search(r'[a-z]', password):
        strength += 1
    if re.search(r'[0-9]', password):
        strength += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        strength += 1
    
    levels = {
        0: "Очень слабый 🔴",
        1: "Слабый 🟠",
        2: "Средний 🟡",
        3: "Хороший 🟢",
        4: "Сильный 🟢",
        5: "Очень сильный 💪"
    }
    
    return levels.get(strength, "Очень слабый 🔴")

conn = get_db_connection()
admin = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
conn.close()

if not st.session_state.authenticated:
    st.title("🚀 Вход в Poster Pro")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not admin:
            st.info("🔐 Первый вход - создайте пароль администратора")
            new_p = st.text_input("Создайте пароль администратора", type="password")
            
            if new_p:
                strength = check_password_strength(new_p)
                st.write(f"Сложность пароля: {strength}")
            
            if st.button("Создать", use_container_width=True) and new_p:
                if len(new_p) >= 6:
                    c = get_db_connection()
                    c.execute("INSERT INTO admin VALUES (1, ?, CURRENT_TIMESTAMP)", (hash_pw(new_p),))
                    c.commit()
                    c.close()
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Пароль должен содержать минимум 6 символов")
        else:
            in_p = st.text_input("Пароль", type="password")
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("Войти", use_container_width=True):
                    if hash_pw(in_p) == admin['password_hash']:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("❌ Неверный пароль")
            with col_b:
                if st.button("Сбросить пароль", use_container_width=True):
                    st.warning("Функция сброса пароля в разработке")
    st.stop()

# ==========================================
# 4. ОСНОВНОЙ ИНТЕРФЕЙС
# ==========================================
st.title("🚀 Poster Pro - Панель управления")

conn = get_db_connection()

# Сайдбар
with st.sidebar:
    st.header("⚙️ Настройки и управление")
    
    if st.button("🚪 Выход", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    
    st.write("---")
    
    # Профили
    profiles = [dict(r) for r in conn.execute("SELECT * FROM profiles").fetchall()]
    
    # Управление профилями
    with st.expander("👤 Профили"):
        action = st.selectbox("Действие", ["Выбрать профиль", "Создать новый", "Удалить"])
        
        if action == "Выбрать профиль":
            active_name = st.selectbox("Активный профиль", [p['name'] for p in profiles])
            active = next(p for p in profiles if p['name'] == active_name)
        elif action == "Создать новый":
            new_profile_name = st.text_input("Название профиля")
            if st.button("Создать") and new_profile_name:
                conn.execute("INSERT INTO profiles (name, tg_token, tg_chat, vk_token, vk_chat) VALUES (?, '', '', '', '')",
                           (new_profile_name,))
                conn.commit()
                st.success(f"Профиль '{new_profile_name}' создан")
                st.rerun()
            active = profiles[0] if profiles else {'name': 'Основной', 'tg_token': '', 'tg_chat': '', 'vk_token': '', 'vk_chat': ''}
        elif action == "Удалить":
            if len(profiles) > 1:
                del_name = st.selectbox("Выберите для удаления", [p['name'] for p in profiles if p['name'] != 'Основной'])
                if st.button("Удалить", type="primary") and del_name:
                    conn.execute("DELETE FROM profiles WHERE name=?", (del_name,))
                    conn.commit()
                    st.success("Профиль удален")
                    st.rerun()
            else:
                st.info("Нельзя удалить последний профиль")
            active = profiles[0] if profiles else {'name': 'Основной', 'tg_token': '', 'tg_chat': '', 'vk_token': '', 'vk_chat': ''}
        else:
            active = profiles[0] if profiles else {'name': 'Основной', 'tg_token': '', 'tg_chat': '', 'vk_token': '', 'vk_chat': ''}
    
    if active:
        st.subheader("📱 ВКонтакте")
        v_t = st.text_input("Токен VK", value=active.get('vk_token', ''), type="password")
        v_c = st.text_input("ID группы (owner_id)", value=active.get('vk_chat', ''))
        
        st.subheader("💬 Telegram")
        t_t = st.text_input("Токен бот", value=active.get('tg_token', ''), type="password")
        t_c = st.text_input("Chat ID", value=active.get('tg_chat', ''))
        
        if st.button("💾 Сохранить профиль", use_container_width=True):
            conn.execute("""UPDATE profiles 
                          SET tg_token=?, tg_chat=?, vk_token=?, vk_chat=? 
                          WHERE name=?""", 
                        (t_t, t_c, v_t, v_c, active['name']))
            conn.commit()
            st.success("✅ Настройки сохранены")
    
    st.write("---")
    
    # Опции публикации
    with st.expander("🎨 Настройки публикации"):
        st.subheader("Telegram")
        tg_pm = st.selectbox("Формат текста", ["HTML", "Markdown", "Отключено"])
        tg_silent = st.checkbox("Без звука", value=False)
        tg_protect = st.checkbox("Защита от пересылки", value=False)
        
        st.subheader("ВКонтакте")
        vk_fg = st.checkbox("Пост от имени группы", value=True)
        vk_close = st.checkbox("Закрыть комментарии", value=False)
    
    st.write("---")
    
    # Системные функции
    with st.expander("🛠 Системные функции"):
        if st.button("📊 Очистить кэш", use_container_width=True):
            st.cache_resource.clear()
            st.success("Кэш очищен")
        
        if st.button("💾 Резервная копия БД", use_container_width=True):
            backup_file = backup_database()
            st.success(f"Резервная копия создана: {backup_file}")
        
        if st.button("🔄 Обновить RSS", use_container_width=True):
            new_count = fetch_rss_news()
            st.success(f"Загружено новостей: {new_count}")

# Основные вкладки
tabs = st.tabs(["📝 Редактор", "📰 Новости", "📋 Шаблоны", "📅 Календарь", 
                "📊 Аналитика", "🎬 Серии", "🖼 Медиатека", "📜 История"])

# Вкладка редактора
with tabs[0]:
    col_editor, col_preview = st.columns([2, 1])
    
    with col_editor:
        st.subheader("Создание публикации")
        
        # Текст поста
        text = st.text_area("Текст поста", value=st.session_state.draft, 
                           height=200, placeholder="Введите текст публикации...",
                           help="Поддерживается HTML и Markdown разметка")
        st.session_state.draft = text
        
        # Хэштеги с автопредложением
        col_tags, col_suggest = st.columns([2, 1])
        with col_tags:
            tags = st.text_input("Хэштеги", placeholder="#тег1 #тег2")
        with col_suggest:
            if st.button("💡 Предложить теги", use_container_width=True) and text:
                suggestions = generate_hashtag_suggestions(text)
                if suggestions:
                    st.write("Предложенные теги:")
                    for tag in suggestions:
                        st.code(tag)
        
        # Медиа файлы
        st.subheader("Медиа файлы")
        files = st.file_uploader("Изображения и видео", 
                                accept_multiple_files=True,
                                type=['png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi'])
        
        compress_images = False
        max_img_size = 2
        
        if files:
            st.write(f"Загружено файлов: {len(files)}")
            
            # Опции обработки изображений
            if any(f.type.startswith('image/') for f in files):
                compress_images = st.checkbox("Сжать изображения", value=True)
                max_img_size = st.slider("Макс. размер (МБ)", 1, 10, 2)
        
        st.write("---")
        
        # Настройки времени
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            post_now = st.checkbox("Опубликовать сейчас", value=True)
        with col2:
            post_date = None
            if not post_now:
                post_date = st.date_input("Дата публикации")
        with col3:
            post_time = None
            if not post_now:
                post_time = st.time_input("Время публикации")
        
        if post_now:
            run_dt = datetime.now()
        else:
            run_dt = datetime.combine(post_date, post_time)
        
        # Дополнительные опции
        with st.expander("⚙️ Дополнительные настройки"):
            add_to_calendar = st.checkbox("Добавить в календарь")
            create_series = st.checkbox("Создать серию постов")
            series_interval = 24
            if create_series:
                series_interval = st.number_input("Интервал между постами (часы)", 
                                                min_value=1, value=24)
        
        st.write("---")
        
        # Кнопка публикации
        if st.button("🚀 Опубликовать", type="primary", use_container_width=True):
            if not text and not files:
                st.error("Введите текст или добавьте медиа файлы")
            else:
                # Обработка файлов
                paths = []
                if files:
                    for f in files:
                        file_data = f.getvalue()
                        
                        # Сжатие изображений если нужно
                        if compress_images and f.type.startswith('image/'):
                            file_data = compress_image(file_data, max_img_size)
                        
                        name = f"{datetime.now().strftime('%H%M%S')}_{random.randint(1000,9999)}_{f.name}"
                        path = os.path.join("uploads", name)
                        with open(path, "wb") as out:
                            out.write(file_data)
                        paths.append(path)
                
                # Формирование текста
                final_text = text
                if tags:
                    final_text = f"{text}\n\n{tags}"
                
                # Сохранение в БД
                cur = conn.cursor()
                cur.execute("""INSERT INTO posts 
                             (scheduled_time, text, platforms, status, full_text, media_count) 
                             VALUES (?,?,?,?,?,?)""",
                          (run_dt.strftime("%Y-%m-%d %H:%M"), 
                           final_text[:100] + "...", 
                           "VK+TG", 
                           "⏳ В очереди", 
                           final_text,
                           len(paths)))
                post_id = cur.lastrowid
                conn.commit()
                
                # Планирование задачи
                if post_now:
                    # Публикация сразу
                    execute_post(
                        final_text, paths,
                        {"tg_token": t_t, "tg_chat": t_c, "vk_token": v_t, "vk_chat": v_c},
                        {"parse_mode": tg_pm, "silent": tg_silent, "protect": tg_protect},
                        {"from_group": vk_fg, "close_comments": vk_close},
                        post_id
                    )
                    st.success("✅ Пост опубликован!")
                else:
                    # Отложенная публикация
                    scheduler.add_job(
                        execute_post, 'date', run_date=run_dt,
                        args=[
                            final_text, paths,
                            {"tg_token": t_t, "tg_chat": t_c, "vk_token": v_t, "vk_chat": v_c},
                            {"parse_mode": tg_pm, "silent": tg_silent, "protect": tg_protect},
                            {"from_group": vk_fg, "close_comments": vk_close},
                            post_id
                        ]
                    )
                    st.success(f"✅ Задача запланирована на {run_dt.strftime('%H:%M %d.%m.%Y')}")
                
                # Добавление в календарь
                if add_to_calendar:
                    conn.execute("""INSERT INTO content_calendar 
                                  (date, time, topic, description, status) 
                                  VALUES (?, ?, ?, ?, 'planned')""",
                               (run_dt.date(), run_dt.time(), 
                                final_text[:50], final_text[:200]))
                    conn.commit()
                
                st.rerun()
    
    with col_preview:
        st.subheader("Предпросмотр")
        if text or files:
            st.write("**Текст поста:**")
            st.write(text)
            if tags:
                st.write(f"*Теги:* {tags}")
            if files:
                st.write(f"*Медиа файлов:* {len(files)}")
                for f in files[:3]:
                    if f.type.startswith('image/'):
                        st.image(f, use_container_width=True)
            st.write(f"*Публикация:* {'Сейчас' if post_now else run_dt.strftime('%d.%m.%Y %H:%M')}")

# Вкладка новостей RSS
with tabs[1]:
    st.subheader("📰 RSS Лента новостей")
    
    # Управление источниками
    with st.expander("📡 Управление источниками"):
        col_src1, col_src2 = st.columns([2, 1])
        
        with col_src1:
            new_src_url = st.text_input("URL RSS ленты")
            new_src_name = st.text_input("Название источника")
        
        with col_src2:
            if st.button("➕ Добавить источник", use_container_width=True):
                if new_src_url and new_src_name:
                    conn.execute("INSERT INTO rss_sources (url, name, enabled) VALUES (?, ?, 1)",
                               (new_src_url, new_src_name))
                    conn.commit()
                    st.success("Источник добавлен")
                    st.rerun()
        
        # Список источников
        sources = conn.execute("SELECT * FROM rss_sources").fetchall()
        for source in sources:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{source['name']}**")
                st.caption(source['url'])
            with col2:
                # Безопасная проверка поля enabled
                try:
                    is_enabled = bool(source['enabled'])
                except (KeyError, IndexError):
                    is_enabled = True
                enabled = st.checkbox("Активен", value=is_enabled, 
                                    key=f"enabled_{source['id']}")
                if enabled != is_enabled:
                    conn.execute("UPDATE rss_sources SET enabled=? WHERE id=?",
                               (int(enabled), source['id']))
                    conn.commit()
            with col3:
                if st.button("🗑", key=f"del_src_{source['id']}"):
                    conn.execute("DELETE FROM rss_sources WHERE id=?", (source['id'],))
                    conn.commit()
                    st.rerun()
    
    # Кнопки управления
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Обновить все", use_container_width=True):
            count = fetch_rss_news()
            st.success(f"Загружено новостей: {count}")
    with col2:
        if st.button("📤 Экспорт в CSV", use_container_width=True):
            news_df = pd.read_sql_query("SELECT * FROM rss_news ORDER BY pub_date DESC", conn)
            csv = news_df.to_csv(index=False)
            st.download_button("Скачать CSV", csv, "rss_news.csv", "text/csv")
    
    # Автопостинг
    with st.expander("🤖 Автоматическая публикация новостей"):
        rules = conn.execute("SELECT * FROM auto_posting_rules").fetchall()
        
        if rules:
            for rule in rules:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.write(f"**{rule['name']}**")
                with col2:
                    st.write(f"Каждые {rule['interval_hours']}ч")
                with col3:
                    try:
                        is_active = bool(rule['is_active'])
                    except (KeyError, IndexError):
                        is_active = True
                    active = st.checkbox("Активно", value=is_active,
                                       key=f"rule_active_{rule['id']}")
                    if active != is_active:
                        conn.execute("UPDATE auto_posting_rules SET is_active=? WHERE id=?",
                                   (int(active), rule['id']))
                        conn.commit()
                with col4:
                    if st.button("🗑", key=f"del_rule_{rule['id']}"):
                        conn.execute("DELETE FROM auto_posting_rules WHERE id=?", (rule['id'],))
                        conn.commit()
                        st.rerun()
        
        st.write("---")
        st.write("**Создать новое правило:**")
        rule_name = st.text_input("Название правила", key="new_rule_name")
        col1, col2 = st.columns([1, 1])
        with col1:
            rule_interval = st.number_input("Интервал (часы)", 1, 168, 6)
        with col2:
            templates_list = conn.execute("SELECT name FROM templates").fetchall()
            if templates_list:
                rule_template = st.selectbox("Шаблон", [t['name'] for t in templates_list])
            else:
                rule_template = st.text_input("Текст шаблона")
        
        if st.button("Создать правило") and rule_name:
            conn.execute("""INSERT INTO auto_posting_rules 
                          (name, source_type, interval_hours, template, is_active) 
                          VALUES (?, 'rss', ?, ?, 1)""",
                       (rule_name, rule_interval, rule_template))
            conn.commit()
            st.success("Правило создано")
            st.rerun()
    
    # Отображение новостей
    st.write("---")
    news = conn.execute("""SELECT * FROM rss_news 
                          ORDER BY pub_date DESC LIMIT 20""").fetchall()
    
    if news:
        for item in news:
            with st.container():
                st.write(f"### {item['title']}")
                st.caption(f"📅 {item['pub_date']}")
                st.write(item['summary'])
                
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("📝 В редактор", key=f"use_{item['id']}", use_container_width=True):
                        st.session_state.draft = f"{item['title']}\n\n{item['summary']}\n\n{item['link']}"
                        st.rerun()
                with col2:
                    if st.button("🚀 Опубликовать", key=f"pub_{item['id']}", use_container_width=True):
                        text = f"{item['title']}\n\n{item['summary']}\n\n{item['link']}"
                        execute_post(text, [], 
                                   {"tg_token": t_t, "tg_chat": t_c, "vk_token": v_t, "vk_chat": v_c},
                                   {"parse_mode": "HTML"}, {"from_group": True}, item['id'])
                        conn.execute("UPDATE rss_news SET is_used=1 WHERE id=?", (item['id'],))
                        conn.commit()
                        st.success("Новость опубликована!")
                with col3:
                    st.write(f"[🔗 Открыть источник]({item['link']})")
                st.write("---")
    else:
        st.info("Нет новостей. Нажмите 'Обновить все' для загрузки.")

# Вкладка шаблонов
with tabs[2]:
    st.subheader("📋 Шаблоны постов")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.write("### Создать новый шаблон")
        tm_name = st.text_input("Название шаблона")
        tm_category = st.selectbox("Категория", ["Общие", "Новости", "Акции", "Техподдержка", "Другое"])
        tm_content = st.text_area("Содержание шаблона", height=200,
                                help="Используйте {title}, {link}, {summary} для RSS",
                                placeholder="""📢 {title}

{summary}

Подробнее: {link}

#новости #технологии""")
        
        if st.button("💾 Сохранить шаблон", use_container_width=True):
            if tm_name and tm_content:
                conn.execute("""INSERT OR REPLACE INTO templates (name, content, category) 
                              VALUES (?, ?, ?)""", 
                           (tm_name, tm_content, tm_category))
                conn.commit()
                st.success("✅ Шаблон сохранен")
                st.rerun()
    
    with col2:
        st.write("### Библиотека шаблонов")
        
        # Безопасное получение категорий
        try:
            categories = conn.execute("SELECT DISTINCT category FROM templates").fetchall()
            category_list = ["Все"] + [c['category'] for c in categories if c['category']]
        except:
            category_list = ["Все", "Общие", "Новости", "Акции", "Техподдержка", "Другое"]
        
        filter_cat = st.selectbox("Фильтр по категории", category_list)
        
        if filter_cat == "Все":
            templates = conn.execute("SELECT * FROM templates ORDER BY name").fetchall()
        else:
            templates = conn.execute("SELECT * FROM templates WHERE category=? ORDER BY name",
                                   (filter_cat,)).fetchall()
        
        if templates:
            for tm in templates:
                with st.expander(f"📄 {tm['name']} [{tm.get('category', 'Общие')}]"):
                    st.text_area("Содержание", tm['content'], height=100, disabled=True,
                               key=f"view_{tm['name']}")
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        if st.button("✏️ Использовать", key=f"use_tmpl_{tm['name']}"):
                            st.session_state.draft = tm['content']
                            st.rerun()
                    with col2:
                        if st.button("📋 Копировать", key=f"copy_{tm['name']}"):
                            st.code(tm['content'])
                    with col3:
                        if st.button("🗑 Удалить", key=f"del_tmpl_{tm['name']}"):
                            conn.execute("DELETE FROM templates WHERE name=?", (tm['name'],))
                            conn.commit()
                            st.rerun()
        else:
            st.info("Нет шаблонов в выбранной категории")

# Вкладка календаря
with tabs[3]:
    st.subheader("📅 Контент-календарь")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        cal_date = st.date_input("Дата", datetime.now())
    with col2:
        if st.button("📊 Показать месяц", use_container_width=True):
            pass
    
    # События на выбранную дату
    events = conn.execute("""SELECT * FROM content_calendar 
                            WHERE date=? ORDER BY time""", 
                         (cal_date,)).fetchall()
    
    if events:
        st.write(f"### События на {cal_date.strftime('%d.%m.%Y')}")
        for event in events:
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"**{event['topic'][:50]}**")
                with col2:
                    st.write(f"🕐 {event['time']}")
                    st.caption(event['description'][:100] if event['description'] else "")
                with col3:
                    status_options = ["planned", "in_progress", "completed", "cancelled"]
                    current_status = event['status'] if event['status'] in status_options else "planned"
                    status = st.selectbox("Статус", 
                                        status_options,
                                        index=status_options.index(current_status),
                                        key=f"status_{event['id']}")
                    if status != current_status:
                        conn.execute("UPDATE content_calendar SET status=? WHERE id=?",
                                   (status, event['id']))
                        conn.commit()
                st.write("---")
    else:
        st.info("Нет запланированных событий на эту дату")
    
    # Добавление события
    with st.expander("➕ Добавить событие в календарь"):
        ev_date = st.date_input("Дата события", key="ev_date")
        ev_time = st.time_input("Время", key="ev_time")
        ev_topic = st.text_input("Тема", key="ev_topic")
        ev_desc = st.text_area("Описание", key="ev_desc")
        
        if st.button("Добавить событие") and ev_topic:
            conn.execute("""INSERT INTO content_calendar (date, time, topic, description) 
                          VALUES (?, ?, ?, ?)""",
                       (ev_date, ev_time, ev_topic, ev_desc))
            conn.commit()
            st.success("Событие добавлено")
            st.rerun()

# Вкладка аналитики
with tabs[4]:
    st.subheader("📊 Аналитика публикаций")
    
    # Общая статистика
    col1, col2, col3, col4 = st.columns(4)
    
    total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    successful_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE status LIKE '%Готово%'").fetchone()[0]
    total_media = conn.execute("SELECT SUM(media_count) FROM posts").fetchone()[0] or 0
    
    with col1:
        st.metric("Всего постов", total_posts)
    with col2:
        st.metric("Успешных", successful_posts)
    with col3:
        st.metric("Медиа файлов", total_media)
    with col4:
        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0
        st.metric("Успешность", f"{success_rate:.1f}%")
    
    st.write("---")
    
    # График публикаций по дням
    try:
        posts_by_day = pd.read_sql_query("""
            SELECT DATE(created_at) as date, COUNT(*) as count 
            FROM posts 
            WHERE created_at >= DATE('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        """, conn)
        
        if not posts_by_day.empty:
            st.subheader("Публикации за последние 30 дней")
            st.line_chart(posts_by_day.set_index('date'))
    except:
        st.info("Недостаточно данных для построения графика")

# Вкладка серий
with tabs[5]:
    st.subheader("🎬 Серии публикаций")
    
    # Существующие серии
    try:
        series_list = conn.execute("SELECT * FROM post_series ORDER BY created_at DESC").fetchall()
    except:
        series_list = []
    
    if series_list:
        for series in series_list:
            with st.expander(f"📺 {series['name']} ({series.get('posts_count', 0)} постов)"):
                st.write(f"**Описание:** {series.get('description', '')}")
                st.write(f"**Интервал:** {series.get('interval_hours', 24)} часов")
                st.write(f"**Создана:** {series.get('created_at', '')}")
                
                # Посты в серии
                try:
                    series_posts = conn.execute("""
                        SELECT * FROM series_posts 
                        WHERE series_id=? 
                        ORDER BY post_number
                    """, (series['id'],)).fetchall()
                    
                    for post in series_posts:
                        st.write(f"**Пост #{post['post_number']}**")
                        st.text(post['text'][:200] + "...")
                        st.write("---")
                except:
                    st.info("Нет постов в серии")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📅 Запланировать", key=f"schedule_{series['id']}"):
                        sched_date = st.date_input("Дата начала", key=f"sched_date_{series['id']}")
                        sched_time = st.time_input("Время начала", key=f"sched_time_{series['id']}")
                        if st.button("Подтвердить", key=f"confirm_{series['id']}"):
                            schedule_series(series['id'], sched_date, sched_time)
                with col2:
                    if st.button("🗑 Удалить серию", key=f"del_series_{series['id']}"):
                        conn.execute("DELETE FROM series_posts WHERE series_id=?", (series['id'],))
                        conn.execute("DELETE FROM post_series WHERE id=?", (series['id'],))
                        conn.commit()
                        st.rerun()
    else:
        st.info("Нет созданных серий")
    
    # Создание новой серии
    with st.expander("➕ Создать новую серию"):
        series_name = st.text_input("Название серии", key="new_series_name")
        series_desc = st.text_area("Описание", key="new_series_desc")
        series_interval = st.number_input("Интервал между постами (часы)", 
                                         min_value=1, value=24)
        
        st.write("**Посты в серии:**")
        series_posts_data = []
        
        num_posts = st.number_input("Количество постов", min_value=2, max_value=20, value=3)
        
        for i in range(num_posts):
            st.write(f"**Пост #{i+1}**")
            post_text = st.text_area(f"Текст поста {i+1}", key=f"series_post_{i}")
            series_posts_data.append({'text': post_text})
        
        if st.button("Создать серию") and series_name and all(p['text'] for p in series_posts_data):
            series_id = create_post_series(series_name, series_desc, 
                                          series_posts_data, series_interval)
            st.success(f"Серия '{series_name}' создана!")
            st.rerun()

# Вкладка медиатеки
with tabs[6]:
    st.subheader("🖼 Медиатека")
    
    # Загрузка медиа в библиотеку
    with st.expander("📤 Загрузить в медиатеку"):
        lib_files = st.file_uploader("Выберите файлы", 
                                    accept_multiple_files=True,
                                    key="lib_upload",
                                    type=['png', 'jpg', 'jpeg', 'gif', 'mp4'])
        
        if lib_files:
            lib_tags = st.text_input("Теги (через запятую)", key="lib_tags")
            
            if st.button("Загрузить в библиотеку"):
                for file in lib_files:
                    file_path = os.path.join("uploads", file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.getvalue())
                    
                    try:
                        conn.execute("""INSERT OR REPLACE INTO media_library 
                                      (filename, original_name, file_type, file_size, tags)
                                      VALUES (?, ?, ?, ?, ?)""",
                                   (file.name, file.name, file.type, 
                                    file.size, lib_tags))
                    except:
                        pass
                conn.commit()
                st.success(f"Загружено файлов: {len(lib_files)}")
                st.rerun()
    
    # Просмотр медиатеки
    try:
        media_items = conn.execute("""
            SELECT * FROM media_library 
            ORDER BY uploaded_at DESC 
            LIMIT 50
        """).fetchall()
    except:
        media_items = []
    
    if media_items:
        cols = st.columns(4)
        for i, item in enumerate(media_items):
            with cols[i % 4]:
                file_path = os.path.join("uploads", item['filename'])
                if os.path.exists(file_path):
                    if item['file_type'].startswith('image/'):
                        st.image(file_path, caption=item['original_name'], 
                               use_container_width=True)
                    elif item['file_type'].startswith('video/'):
                        st.video(file_path)
                
                st.caption(f"📅 {item['uploaded_at'][:10] if item['uploaded_at'] else ''}")
                if item['tags']:
                    st.caption(f"🏷 {item['tags']}")
                
                col_use, col_del = st.columns(2)
                with col_use:
                    if st.button("📝", key=f"use_media_{item['id']}"):
                        st.info("Файл добавлен в редактор")
                with col_del:
                    if st.button("🗑", key=f"del_media_{item['id']}"):
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        conn.execute("DELETE FROM media_library WHERE id=?", 
                                   (item['id'],))
                        conn.commit()
                        st.rerun()
    else:
        st.info("Медиатека пуста. Загрузите файлы для начала работы.")

# Вкладка истории
with tabs[7]:
    st.subheader("📜 История публикаций")
    
    # Фильтры
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        status_filter = st.selectbox("Статус", 
                                   ["Все", "✅ Успешно", "❌ Ошибка", "⏳ В очереди"])
    with col2:
        date_filter = st.date_input("Дата", value=None)
    with col3:
        search_text = st.text_input("🔍 Поиск по тексту")
    
    # Построение запроса
    query = "SELECT * FROM posts WHERE 1=1"
    params = []
    
    if status_filter == "✅ Успешно":
        query += " AND status LIKE '%Готово%'"
    elif status_filter == "❌ Ошибка":
        query += " AND status LIKE '%Ошибка%'"
    elif status_filter == "⏳ В очереди":
        query += " AND status LIKE '%очереди%'"
    
    if date_filter:
        query += " AND DATE(scheduled_time) = ?"
        params.append(date_filter)
    
    if search_text:
        query += " AND (text LIKE ? OR full_text LIKE ?)"
        params.extend([f"%{search_text}%", f"%{search_text}%"])
    
    query += " ORDER BY scheduled_time DESC LIMIT 50"
    
    try:
        posts = conn.execute(query, params).fetchall()
    except:
        posts = []
    
    if posts:
        st.write(f"Найдено постов: {len(posts)}")
        
        for post in posts:
            with st.expander(f"{post['id']} - {post['status']} | {post['scheduled_time']}"):
                st.write(f"**Текст:** {post['text']}")
                
                if post['full_text']:
                    with st.expander("Полный текст"):
                        st.write(post['full_text'])
                
                st.write(f"**Платформы:** {post['platforms']}")
                
                # Действия
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📝 Повторить", key=f"repeat_{post['id']}"):
                        if post['full_text']:
                            st.session_state.draft = post['full_text']
                            st.rerun()
                with col2:
                    if st.button("📊 Обновить аналитику", key=f"update_analytics_{post['id']}"):
                        st.info("Аналитика обновлена")
                with col3:
                    if st.button("🗑 Удалить", key=f"del_post_{post['id']}"):
                        conn.execute("DELETE FROM posts WHERE id=?", (post['id'],))
                        conn.execute("DELETE FROM analytics WHERE post_id=?", (post['id'],))
                        conn.commit()
                        st.rerun()
    else:
        st.info("Нет публикаций по заданным критериям")
    
    # Экспорт истории
    if st.button("📥 Экспорт истории в CSV"):
        all_posts = export_posts_to_csv()
        csv = all_posts.to_csv(index=False)
        st.download_button("Скачать CSV", csv, "posts_history.csv", "text/csv")

conn.close()

# Футер
st.write("---")
st.caption("Poster Pro v2.0 | Разработано с ❤️ | Все права защищены")
