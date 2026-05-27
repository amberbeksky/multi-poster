import streamlit as st
import vk_api
import telebot
import tempfile
import os

# Настройка страницы на всю ширину для вида админ-панели
st.set_page_config(page_title="Multi-Poster Dashboard", layout="wide", page_icon="⚙️")

st.title("🛠 Панель управления: Multi-Poster")
st.write("Централизованная отправка контента с вложениями")

# Боковая панель для технических настроек
with st.sidebar:
    st.header("🔑 Доступы API")
    tg_token = st.text_input("Telegram Token", type="password")
    tg_chat = st.text_input("Telegram Chat ID")
    vk_token = st.text_input("VK Access Token", type="password")
    vk_chat = st.text_input("VK Group ID (число без минуса)")
    
    st.divider()
    st.info("Токены активны только в текущей сессии браузера для обеспечения безопасности.")

# Основная рабочая область разбита на колонки
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Контент поста")
    post_text = st.text_area("Текст сообщения", height=250, placeholder="Введите текст поста...")
    
    # Загрузчик файлов
    uploaded_file = st.file_uploader("Прикрепить изображение", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        st.image(uploaded_file, caption="Превью изображения", use_container_width=True)

with col2:
    st.subheader("⚙️ Статус и управление")
    st.info("Заполните текст, прикрепите медиафайлы и нажмите кнопку запуска.")
    
    # Кнопка отправки
    submit_btn = st.button("🚀 Отправить во все сети", use_container_width=True, type="primary")
    
    # Контейнер для вывода результатов
    result_container = st.container()

# Логика отправки
if submit_btn:
    if not post_text and not uploaded_file:
        result_container.error("Ошибка: Добавьте текст или изображение для отправки!")
    else:
        with result_container:
            st.write("**Статус публикации:**")
            
            # --- TELEGRAM ---
            if tg_token and tg_chat:
                try:
                    bot = telebot.TeleBot(tg_token)
                    if uploaded_file:
                        bot.send_photo(tg_chat, uploaded_file.getvalue(), caption=post_text)
                    else:
                        bot.send_message(tg_chat, post_text)
                    st.success("✅ Telegram: Опубликовано")
                except Exception as e:
                    st.error(f"❌ Ошибка Telegram: {e}")
            else:
                st.warning("⚠️ Telegram: Не указаны API доступы")

            # --- VKONTAKTE ---
            if vk_token and vk_chat:
                try:
                    vk_session = vk_api.VkApi(token=vk_token)
                    vk = vk_session.get_api()
                    
                    attachment_str = ""
                    
                    if uploaded_file:
                        # VK требует физический файл, создаем временный
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name
                        
                        upload = vk_api.VkUpload(vk_session)
                        photo = upload.photo_wall(photos=tmp_path)[0]
                        attachment_str = f"photo{photo['owner_id']}_{photo['id']}"
                        
                        # Удаляем временный файл с сервера
                        os.remove(tmp_path)
                    
                    vk.wall.post(owner_id=-int(vk_chat), message=post_text, attachments=attachment_str)
                    st.success("✅ ВКонтакте: Опубликовано")
                except Exception as e:
                    st.error(f"❌ Ошибка VK: {e}")
            else:
                st.warning("⚠️ ВКонтакте: Не указаны API доступы")
