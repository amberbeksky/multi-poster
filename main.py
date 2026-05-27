import streamlit as st
import vk_api
import telebot
from telebot.types import InputMediaPhoto
import tempfile
import os
from datetime import datetime
import time
import pandas as pd

# Базовая настройка
st.set_page_config(page_title="Multi-Poster ULTIMATE", layout="wide", page_icon="⚡")

# Инициализация хранилища сессии (базы данных на время работы)
if 'post_history' not in st.session_state:
    st.session_state.post_history = []
if 'templates' not in st.session_state:
    st.session_state.templates = {
        "Услуги IT": "Ремонт ПК, сборка, настройка ViPNet и КриптоПро. Быстро и надежно.\n\n#COMPASTERVRN",
        "Арт": "Новая генерация. Стиль: 90s Polaroid, реалистичные текстуры.",
    }

st.title("⚡ Multi-Poster ULTIMATE")
st.write("Максимальная мощность: шаблоны, экспорт CSV, тихие посты и защита контента.")

# БОКОВАЯ ПАНЕЛЬ - НАСТРОЙКИ API И ТУМБЛЕРЫ
with st.sidebar:
    st.header("🔑 Доступы API")
    tg_token = st.text_input("Telegram Token", type="password")
    tg_chat = st.text_input("Telegram Chat ID")
    vk_token = st.text_input("VK Access Token", type="password")
    vk_chat = st.text_input("VK Group ID (цифры)")
    
    st.divider()
    
    st.header("⚙️ Telegram Опции")
    tg_parse_mode = st.selectbox("Форматирование", ["Markdown", "HTML", "Отключено"])
    tg_silent = st.checkbox("Тихое сообщение (без звука)")
    tg_protect = st.checkbox("Защита от пересылки")
    tg_no_preview = st.checkbox("Отключить превью ссылок")
    
    st.divider()
    
    st.header("⚙️ ВКонтакте Опции")
    vk_from_group = st.checkbox("Пост от имени группы", value=True)
    vk_close_comments = st.checkbox("Закрыть комментарии")
    
    st.divider()
    st.caption("Разработано: Zelenkov Danil Vadimovich, junior DBA")

# РАБОЧИЕ ВКЛАДКИ
tab_editor, tab_templates, tab_analytics = st.tabs(["🚀 Редактор", "📁 Шаблоны", "📊 Статистика"])

with tab_editor:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Быстрая загрузка шаблона
        template_choice = st.selectbox("Загрузить шаблон", ["- Свой текст -"] + list(st.session_state.templates.keys()))
        default_text = st.session_state.templates.get(template_choice, "") if template_choice != "- Свой текст -" else ""
        
        post_text = st.text_area("Текст сообщения", value=default_text, height=250)
        
        col_tags, col_delay = st.columns(2)
        with col_tags:
            hashtags = st.text_input("Хэштеги", placeholder="#работа #новости")
        with col_delay:
            delay_sec = st.slider("Задержка отправки (сек)", 0, 10, 0)
            
        uploaded_files = st.file_uploader("Изображения (поддерживается мультизагрузка)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
    with col2:
        st.subheader("Статус")
        
        # Проверка лимитов Telegram
        text_length = len(post_text + hashtags)
        if uploaded_files and text_length > 1024:
            st.warning(f"⚠️ Текст с фото ({text_length} симв.) превышает лимит TG (1024). Текст обрежется!")
        elif not uploaded_files and text_length > 4096:
            st.warning(f"⚠️ Текст ({text_length} симв.) превышает лимит TG (4096).")
        else:
            st.success("✅ Длина текста в норме")

        submit_btn = st.button("🔥 ЗАПУСТИТЬ РАССЫЛКУ", use_container_width=True, type="primary")
        result_container = st.container()

with tab_templates:
    st.subheader("Управление шаблонами")
    new_tpl_name = st.text_input("Название нового шаблона")
    new_tpl_text = st.text_area("Текст нового шаблона")
    if st.button("Сохранить шаблон"):
        if new_tpl_name and new_tpl_text:
            st.session_state.templates[new_tpl_name] = new_tpl_text
            st.success(f"Шаблон '{new_tpl_name}' сохранен!")
            st.rerun()
            
    st.divider()
    st.write("Текущие сохраненные шаблоны:")
    st.json(st.session_state.templates)

with tab_analytics:
    st.subheader("История публикаций")
    if not st.session_state.post_history:
        st.info("Пока нет данных для отображения.")
    else:
        # Превращаем историю в таблицу
        df = pd.DataFrame(st.session_state.post_history)
        st.dataframe(df, use_container_width=True)
        
        # Кнопка экспорта в CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Скачать отчет (CSV)",
            data=csv,
            file_name=f"smm_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

# ЛОГИКА ОТПРАВКИ
final_text = post_text
if hashtags:
    final_text += f"\n\n{hashtags}"

if submit_btn:
    if not final_text.strip() and not uploaded_files:
        result_container.error("Пустой пост! Добавьте текст или фото.")
    else:
        with result_container:
            if delay_sec > 0:
                with st.spinner(f"Ожидание {delay_sec} секунд..."):
                    time.sleep(delay_sec)
                    
            success_platforms = []
            
            # ОТПРАВКА TELEGRAM
            if tg_token and tg_chat:
                try:
                    bot = telebot.TeleBot(tg_token)
                    pm = None if tg_parse_mode == "Отключено" else tg_parse_mode
                    
                    if not uploaded_files:
                        bot.send_message(
                            tg_chat, final_text, parse_mode=pm, 
                            disable_notification=tg_silent, 
                            protect_content=tg_protect,
                            disable_web_page_preview=tg_no_preview
                        )
                    elif len(uploaded_files) == 1:
                        bot.send_photo(
                            tg_chat, uploaded_files[0].getvalue(), 
                            caption=final_text[:1024], parse_mode=pm,
                            disable_notification=tg_silent,
                            protect_content=tg_protect
                        )
                    else:
                        media = []
                        for i, file in enumerate(uploaded_files):
                            if i == 0:
                                media.append(InputMediaPhoto(file.getvalue(), caption=final_text[:1024], parse_mode=pm))
                            else:
                                media.append(InputMediaPhoto(file.getvalue()))
                        bot.send_media_group(
                            tg_chat, media, 
                            disable_notification=tg_silent, 
                            protect_content=tg_protect
                        )
                        
                    st.success("✅ TG: Отправлено")
                    success_platforms.append("Telegram")
                except Exception as e:
                    st.error(f"❌ Ошибка TG: {e}")

            # ОТПРАВКА VKONTAKTE
            if vk_token and vk_chat:
                try:
                    vk_session = vk_api.VkApi(token=vk_token)
                    vk = vk_session.get_api()
                    upload = vk_api.VkUpload(vk_session)
                    attachments = []
                    
                    if uploaded_files:
                        for file in uploaded_files:
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                tmp.write(file.getvalue())
                                tmp_path = tmp.name
                            photo = upload.photo_wall(photos=tmp_path)[0]
                            attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
                            os.remove(tmp_path)
                    
                    vk.wall.post(
                        owner_id=-int(vk_chat), 
                        message=final_text, 
                        attachments=",".join(attachments) if attachments else "",
                        from_group=1 if vk_from_group else 0,
                        close_comments=1 if vk_close_comments else 0
                    )
                    st.success("✅ VK: Отправлено")
                    success_platforms.append("ВКонтакте")
                except Exception as e:
                    st.error(f"❌ Ошибка VK: {e}")
            
            # ЗАПИСЬ В БАЗУ ДАННЫХ (СЕССИЮ)
            if success_platforms:
                st.session_state.post_history.append({
                    "Дата/Время": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Платформы": " + ".join(success_platforms),
                    "Текст": final_text[:50] + "...",
                    "Фото": len(uploaded_files) if uploaded_files else 0
                })
