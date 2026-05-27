import streamlit as st
import vk_api
import telebot
from telebot.types import InputMediaPhoto
import tempfile
import os
from datetime import datetime
import time
import pandas as pd
import re

# ==========================================
# 1. БАЗОВАЯ НАСТРОЙКА И СЕССИИ (Junior DBA level)
# ==========================================
st.set_page_config(page_title="Multi-Poster GOD MODE", layout="wide", page_icon="⚡")

# Инициализация "базы данных" в кэше сессии
if 'profiles' not in st.session_state:
    st.session_state.profiles = {
        "Основной": {"tg_token": "", "tg_chat": "", "vk_token": "", "vk_chat": ""}
    }
if 'active_profile' not in st.session_state:
    st.session_state.active_profile = "Основной"
if 'draft' not in st.session_state:
    st.session_state.draft = ""
if 'post_history' not in st.session_state:
    st.session_state.post_history = []
if 'templates' not in st.session_state:
    st.session_state.templates = {
        "Прайс IT-Услуг": "🖥 Ремонт ПК, чистка, замена термопасты.\nНастройка ViPNet, КриптоПро и ЭЦП под ключ.\n\nОбращайтесь в личные сообщения!\n#COMPASTERVRN #ремонтпк",
        "Уведомление (Работа)": "Внимание сотрудников!\nРасчетные листки за текущий месяц сформированы и доступны в электронном виде.\n\nПросьба проверить почту.",
        "Арт-Генерация": "Новый концепт. \nСтиль: 90s Polaroid, кинематографичный свет, реалистичные текстуры."
    }

st.title("⚡ Multi-Poster GOD MODE")
st.write("Сверхмощный SMM-комбайн: Мультиаккаунты, SEO-анализ, UTM-метки и Шаблоны.")

# ==========================================
# 2. БОКОВАЯ ПАНЕЛЬ - УПРАВЛЕНИЕ ПРОФИЛЯМИ
# ==========================================
with st.sidebar:
    st.header("🗂 Профили API")
    
    # Выбор активного профиля
    profile_names = list(st.session_state.profiles.keys())
    selected_profile = st.selectbox("Активный профиль:", profile_names, index=profile_names.index(st.session_state.active_profile))
    st.session_state.active_profile = selected_profile
    
    # Загружаем данные активного профиля
    active_data = st.session_state.profiles[selected_profile]
    
    tg_token = st.text_input("Telegram Token", value=active_data.get("tg_token", ""), type="password")
    tg_chat = st.text_input("Telegram Chat ID", value=active_data.get("tg_chat", ""))
    vk_token = st.text_input("VK Access Token", value=active_data.get("vk_token", ""), type="password")
    vk_chat = st.text_input("VK Group ID", value=active_data.get("vk_chat", ""))
    
    # Автосохранение при изменении полей
    if st.button("💾 Сохранить доступы в профиль"):
        st.session_state.profiles[selected_profile] = {
            "tg_token": tg_token, "tg_chat": tg_chat, "vk_token": vk_token, "vk_chat": vk_chat
        }
        st.success("Доступы сохранены!")
        
    st.divider()
    st.header("⚙️ Опции публикации")
    tg_parse_mode = st.selectbox("TG Форматирование", ["Markdown", "HTML", "Отключено"])
    tg_silent = st.checkbox("Тихое сообщение (без звука)")
    vk_from_group = st.checkbox("ВК: Пост от имени группы", value=True)

# ==========================================
# 3. РАБОЧИЕ ПРОСТРАНСТВА (ВКЛАДКИ)
# ==========================================
tab_editor, tab_seo, tab_templates, tab_analytics = st.tabs(["🚀 Редактор", "🛠 SEO & UTM", "📁 Шаблоны", "📊 Статистика"])

# --- ВКЛАДКА: РЕДАКТОР ---
with tab_editor:
    col1, col2 = st.columns([2, 1])
    with col1:
        # Умный черновик
        post_text = st.text_area("Текст сообщения", value=st.session_state.draft, height=250, key="text_editor")
        st.session_state.draft = post_text # Автосейв
        
        col_tags, col_delay = st.columns(2)
        with col_tags:
            hashtags = st.text_input("Хэштеги (через пробел)", placeholder="#новости #блог")
        with col_delay:
            delay_sec = st.slider("Отложенный старт (сек)", 0, 15, 0)
            
        uploaded_files = st.file_uploader("Изображения (Мультизагрузка)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
    with col2:
        st.subheader("Монитор лимитов")
        full_len = len(post_text + hashtags)
        
        if uploaded_files and full_len > 1024:
            st.error(f"⚠️ Текст с фото ({full_len}/1024) превышает лимит TG! Капшн обрежется.")
        elif not uploaded_files and full_len > 4096:
            st.error(f"⚠️ Текст ({full_len}/4096) превышает лимит TG.")
        else:
            st.success(f"✅ Длина в норме ({full_len} симв.)")
            
        st.info("Палитра SMM: 🔥 🚀 ⚡ ✅ ❌ 📌 💡 ⚠️ 💬 📞 🖥 ⚙️")
        
        submit_btn = st.button("🔥 ОПУБЛИКОВАТЬ ВЕЗДЕ", use_container_width=True, type="primary")
        result_container = st.container()

# --- ВКЛАДКА: SEO & UTM ---
with tab_seo:
    st.subheader("Генератор UTM-меток")
    utm_url = st.text_input("Целевая ссылка (URL)")
    c1, c2, c3 = st.columns(3)
    with c1: utm_source = st.text_input("Source (источник)", placeholder="vk, tg")
    with c2: utm_medium = st.text_input("Medium (тип трафика)", placeholder="social, cpc")
    with c3: utm_campaign = st.text_input("Campaign (название кампании)")
    
    if utm_url and utm_source:
        final_utm = f"{utm_url}?utm_source={utm_source}&utm_medium={utm_medium}&utm_campaign={utm_campaign}"
        st.code(final_utm, language="text")
        
    st.divider()
    st.subheader("SEO Анализатор черновика")
    if post_text:
        words = len(post_text.split())
        tags_count = len(re.findall(r'#\w+', post_text + " " + hashtags))
        cta_words = ['купить', 'заказать', 'звоните', 'ссылка', 'переходи', 'пишите']
        has_cta = any(cta in post_text.lower() for cta in cta_words)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Слов", words)
        m2.metric("Хэштегов", tags_count, delta="- Теневой бан!" if tags_count > 10 else "Ок", delta_color="inverse")
        m3.metric("Призыв к действию (CTA)", "Есть ✅" if has_cta else "Нет ❌")

# --- ВКЛАДКА: ШАБЛОНЫ ---
with tab_templates:
    st.subheader("Быстрая загрузка")
    cols = st.columns(3)
    for i, (t_name, t_text) in enumerate(st.session_state.templates.items()):
        with cols[i % 3]:
            st.info(f"**{t_name}**")
            st.caption(t_text[:100] + "...")
            if st.button("Загрузить", key=f"load_{t_name}"):
                st.session_state.draft = t_text
                st.rerun()

# --- ВКЛАДКА: СТАТИСТИКА ---
with tab_analytics:
    if not st.session_state.post_history:
        st.info("История пуста.")
    else:
        df = pd.DataFrame(st.session_state.post_history)
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Скачать логи (CSV)", data=csv, file_name="smm_logs.csv", mime="text/csv")

# ==========================================
# 4. ЯДРО ОТПРАВКИ 
# ==========================================
final_text = post_text
if hashtags:
    final_text += f"\n\n{hashtags}"

if submit_btn:
    if not final_text.strip() and not uploaded_files:
        result_container.error("Ошибка: Пост пуст!")
    else:
        with result_container:
            if delay_sec > 0:
                with st.spinner(f"Таймер старта: {delay_sec} сек..."):
                    time.sleep(delay_sec)
                    
            success_platforms = []
            
            # --- TELEGRAM ---
            if tg_token and tg_chat:
                try:
                    bot = telebot.TeleBot(tg_token)
                    pm = None if tg_parse_mode == "Отключено" else tg_parse_mode
                    
                    if not uploaded_files:
                        bot.send_message(tg_chat, final_text, parse_mode=pm, disable_notification=tg_silent)
                    elif len(uploaded_files) == 1:
                        bot.send_photo(tg_chat, uploaded_files[0].getvalue(), caption=final_text[:1024], parse_mode=pm, disable_notification=tg_silent)
                    else:
                        media = []
                        for i, file in enumerate(uploaded_files):
                            caption = final_text[:1024] if i == 0 else None
                            media.append(InputMediaPhoto(file.getvalue(), caption=caption, parse_mode=pm))
                        bot.send_media_group(tg_chat, media, disable_notification=tg_silent)
                        
                    st.success("✅ TG: Отправлено")
                    success_platforms.append("Telegram")
                except Exception as e:
                    st.error(f"❌ Ошибка TG: {e}")

            # --- VKONTAKTE ---
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
                        from_group=1 if vk_from_group else 0
                    )
                    st.success("✅ VK: Отправлено")
                    success_platforms.append("ВКонтакте")
                except Exception as e:
                    st.error(f"❌ Ошибка VK: {e}")
            
            if success_platforms:
                st.session_state.post_history.append({
                    "Время": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Профиль": selected_profile,
                    "Платформы": " + ".join(success_platforms),
                    "Текст": final_text[:40] + "...",
                    "Фото": len(uploaded_files) if uploaded_files else 0
                })
