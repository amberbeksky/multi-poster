import flet as ft
import vk_api
import telebot
import os

def main(page: ft.Page):
    page.title = "Multi-Poster"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = "auto"
    page.padding = 20

    # Поля ввода
    tg_token = ft.TextField(label="Telegram Bot Token", password=True, can_reveal_password=True)
    tg_chat = ft.TextField(label="Telegram Chat ID (канал или личка)")
    vk_token = ft.TextField(label="VK Access Token", password=True, can_reveal_password=True)
    vk_chat = ft.TextField(label="VK Group ID (только цифры)")
    
    post_text = ft.TextField(label="Текст поста", multiline=True, min_lines=5, border_color="#3b82f6")
    status_text = ft.Text()

    # Загрузка настроек из памяти браузера
    def load_settings():
        tg_token.value = page.client_storage.get("tg_token") or ""
        tg_chat.value = page.client_storage.get("tg_chat") or ""
        vk_token.value = page.client_storage.get("vk_token") or ""
        vk_chat.value = page.client_storage.get("vk_chat") or ""
        page.update()

    def send_post(e):
        if not post_text.value:
            status_text.value = "Введите текст поста!"
            status_text.color = ft.colors.RED
            page.update()
            return

        # Сохраняем токены, чтобы не вводить их завтра
        page.client_storage.set("tg_token", tg_token.value)
        page.client_storage.set("tg_chat", tg_chat.value)
        page.client_storage.set("vk_token", vk_token.value)
        page.client_storage.set("vk_chat", vk_chat.value)

        status_text.value = "Публикация..."
        status_text.color = ft.colors.BLUE
        page.update()

        results = []
        
        # Telegram
        if tg_token.value and tg_chat.value:
            try:
                bot = telebot.TeleBot(tg_token.value)
                bot.send_message(tg_chat.value, post_text.value)
                results.append("✅ Telegram: Успешно")
            except Exception as ex:
                results.append(f"❌ Telegram: {str(ex)}")

        # VK
        if vk_token.value and vk_chat.value:
            try:
                vk_session = vk_api.VkApi(token=vk_token.value)
                vk = vk_session.get_api()
                vk.wall.post(owner_id=-int(vk_chat.value), message=post_text.value)
                results.append("✅ VK: Успешно")
            except Exception as ex:
                results.append(f"❌ VK: {str(ex)}")

        status_text.value = "\n".join(results)
        page.update()

    # Сборка интерфейса
    page.add(
        ft.Text("Настройки API", size=20, weight="bold"),
        ft.ExpansionTile(
            title=ft.Text("Показать/скрыть настройки"),
            controls=[ft.Column([tg_token, tg_chat, vk_token, vk_chat])]
        ),
        ft.Divider(),
        ft.Text("Создание поста", size=20, weight="bold"),
        post_text,
        ft.ElevatedButton("Опубликовать везде", icon=ft.icons.SEND, on_click=send_post),
        status_text
    )
    load_settings()

if __name__ == "__main__":
    # Порт для Render
    port = int(os.getenv("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port)