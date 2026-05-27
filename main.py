import streamlit as st
import vk_api
import telebot
from telebot.types import InputMediaPhoto
import tempfile
import os
from datetime import datetime

# Настройка страницы
st.set_page_config(page_title="Multi-Poster PRO", layout="wide", page_icon="🔥")

# Инициализация хранилища сессии для истории постов
if 'post_history' not in st.session_state:
    st.session_state.post_history = []

st.title("🔥 Multi-Poster PRO")
st.write("Максимальный функционал: мульти-медиа, форматирование и история.")

# --- БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
with st.sidebar:
    st.header("🔑 Доступы API")
    tg_token = st.text_input("Telegram Token", type="password")
    tg_chat = st.text_input("Telegram Chat ID")
    vk_token = st.text_input("VK Access Token", type="password")
    vk_chat = st.text_input("VK Group ID (число без минуса)")
    
    st.divider()
    st.header("⚙️ Опции публикации")
    tg_parse_mode = st.selectbox("Форматирование Telegram", options=["Отключено", "Markdown", "HTML"])
    add_watermark = st.checkbox("Добавлять подпись в конце", value=False)
    watermark_text = st.text_input("Текст подписи", value="Опубликовано через Multi-Poster") if add_watermark else ""

# --- ОСНОВНАЯ РАБОЧАЯ ЗОНА (ВКЛАДКИ) ---
tab_editor, tab_preview, tab_history = st.tabs(["📝 Редактор", "👀 Предпросмотр", "📖 История публикаций"])

with tab_editor:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        post_text = st.text_area("Текст сообщения", height=200, placeholder="Введите текст поста...")
        hashtags = st.text_input("Хэштеги (через пробел)", placeholder="#новости #блог")
        
        # Поддержка загрузки нескольких файлов
        uploaded_files = st.file_uploader("Прикрепить изображения (можно несколько)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    
    with col2:
        st.info("💡 Совет: используйте Markdown для выделения текста в Telegram (**жирный**, *курсив*).")
        submit_btn = st.button("🚀 Отправить во все сети", use_container_width=True, type="primary")
        result_container = st.container()

# Формирование финального текста
final_text = post_text
if hashtags:
    final_text += f"\n\n{hashtags}"
if add_watermark:
    final_text += f"\n\n_{watermark_text}_"

with tab_preview:
    st.subheader("Так будет выглядеть текст:")
    st.write(final_text)
    if uploaded_files:
        st.subheader(f"Прикреплено изображений: {len(uploaded_files)}")
        cols = st.columns(min(len(uploaded_files), 4))
        for idx, file in enumerate(uploaded_files):
            cols[idx % 4].image(file, use_container_width=True)

with tab_history:
    st.subheader("История за текущую сессию")
    if not st.session_state.post_history:
        st.write("Пока ничего не опубликовано.")
    else:
        for item in reversed(st.session_state.post_history):
            st.success(f"Время: {item['time']} | Платформы: {item['platforms']}")
            st.caption(item['text'][:100] + "...")

# --- ЛОГИКА ОТПРАВКИ ---
if submit_btn:
    if not final_text.strip() and not uploaded_files:
        result_container.error("Ошибка: Добавьте текст или изображение!")
    else:
        with result_container:
            st.write("**Статус публикации:**")
            success_platforms = []
            
            # --- TELEGRAM ---
            if tg_token and tg_chat:
                try:
                    bot = telebot.TeleBot(tg_token)
                    pm = None if tg_parse_mode == "Отключено" else tg_parse_mode
                    
                    if not uploaded_files:
                        bot.send_message(tg_chat, final_text, parse_mode=pm)
                    elif len(uploaded_files) == 1:
                        bot.send_photo(tg_chat, uploaded_files[0].getvalue(), caption=final_text, parse_mode=pm)
                    else:
                        # Отправка альбома (MediaGroup)
                        media = []
                        for i, file in enumerate(uploaded_files):
                            if i == 0:
                                media.append(InputMediaPhoto(file.getvalue(), caption=final_text, parse_mode=pm))
                            else:
                                media.append(InputMediaPhoto(file.getvalue()))
                        bot.send_media_group(tg_chat, media)
                        
                    st.success("✅ Telegram: Успешно")
                    success_platforms.append("Telegram")
                except Exception as e:
                    st.error(f"❌ Ошибка TG: {e}")
            else:
                st.warning("⚠️ TG: Нет токенов")

            # --- VKONTAKTE ---
            if vk_token and vk_chat:
                try:
                    vk_session = vk_api.VkApi(token=vk_token)
                    vk = vk_session.get_api()
                    upload = vk_api.VkUpload(vk_session)
                    
                    attachments = []
                    
                    # Обработка нескольких фото для ВК
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
                        attachments=",".join(attachments) if attachments else ""
                    )
                    st.success("✅ ВКонтакте: Успешно")
                    success_platforms.append("ВКонтакте")
                except Exception as e:
                    st.error(f"❌ Ошибка VK: {e}")
            else:
                st.warning("⚠️ VK: Нет токенов")
            
            # Запись в историю
            if success_platforms:
                st.session_state.post_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "text": final_text,
                    "platforms": ", ".join(success_platforms)
                })
