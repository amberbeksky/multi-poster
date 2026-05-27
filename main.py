import streamlit as st
import vk_api
import telebot

# Настройка страницы
st.set_page_config(page_title="Multi-Poster", layout="centered")

st.title("🚀 Multi-Poster")
st.write("Публикация в Telegram и ВК одновременно")

# Используем боковую панель для настроек
with st.sidebar:
    st.header("Настройки API")
    tg_token = st.text_input("Telegram Bot Token", type="password")
    tg_chat = st.text_input("Telegram Chat ID")
    vk_token = st.text_input("VK Access Token", type="password")
    vk_chat = st.text_input("VK Group ID (цифры)")
    st.warning("Вводите данные при каждом сеансе — они не хранятся на сервере.")

# Основная часть
post_text = st.text_area("Текст поста", height=200)

if st.button("Опубликовать", use_container_width=True):
    if not post_text:
        st.error("Напишите текст поста!")
    else:
        # Отправка в Telegram
        if tg_token and tg_chat:
            try:
                bot = telebot.TeleBot(tg_token)
                bot.send_message(tg_chat, post_text)
                st.success("✅ Telegram: Отправлено!")
            except Exception as e:
                st.error(f"❌ Ошибка Telegram: {e}")
        
        # Отправка в ВК
        if vk_token and vk_chat:
            try:
                vk_session = vk_api.VkApi(token=vk_token)
                vk = vk_session.get_api()
                # Для групп ID должен быть отрицательным
                vk.wall.post(owner_id=-int(vk_chat), message=post_text)
                st.success("✅ ВК: Отправлено!")
            except Exception as e:
                st.error(f"❌ Ошибка ВК: {e}")
