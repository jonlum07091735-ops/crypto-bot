import os
import requests
import time
import threading
from datetime import datetime
from bs4 import BeautifulSoup
import urllib.parse

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
API = "https://api.telegram.org/bot" + TOKEN
CHANNEL = "@cryptoainovosti"

pending = {}
settings = {"auto": False}
chat_history = {}

def send(chat, text, markup=None):
    data = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    try:
        requests.post(API + "/sendMessage", json=data, timeout=10)
    except:
        pass

def send_photo(chat, photo_url, caption="", markup=None):
    data = {"chat_id": chat, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    try:
        requests.post(API + "/sendPhoto", json=data, timeout=15)
    except:
        pass

def ai(messages):
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + GROQ_KEY, "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 800},
            timeout=30
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "Извини, AI временно недоступен: " + str(e)

def generate_image(prompt):
    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=512&nologo=true"
        return url
    except:
        return None

def get_image_prompt(news_list):
    titles = " | ".join([n["title"] for n in news_list[:3]])
    prompt = ai([
        {"role": "system", "content": "Generate a short English image prompt (max 20 words) for a crypto news article illustration. Style: modern, digital, financial. No text in image."},
        {"role": "user", "content": "News: " + titles}
    ])
    return prompt[:200]

def get_news():
    news = []
    try:
        r = requests.get(
            "https://cryptopanic.com/api/v1/posts/?auth_token=public&kind=news&limit=10",
            timeout=10
        )
        for i in r.json().get("results", [])[:5]:
            news.append({"title": i["title"], "source": "CryptoPanic"})
    except:
        pass
    for url, tag in [
        ("https://coindesk.com", "h4"),
        ("https://cointelegraph.com", "h2"),
        ("https://decrypt.co", "h3")
    ]:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for t in soup.find_all(tag)[:2]:
                text = t.get_text().strip()
                if len(text) > 20:
                    news.append({"title": text, "source": url.replace("https://", "")})
        except:
            pass
    if not news:
        news = [
            {"title": "Bitcoin continues growth amid institutional buying", "source": "manual"},
            {"title": "Ethereum network update attracts new developers", "source": "manual"},
            {"title": "Crypto market shows positive dynamics", "source": "manual"}
        ]
    return news[:8]

def write_post(news_list):
    titles = " | ".join([n["title"] for n in news_list])
    return ai([
        {"role": "system", "content": "Ты крипто эксперт и автор популярного Telegram канала. Пиши интересные, информативные посты на русском языке. Используй эмодзи. Пост должен быть 150-200 слов."},
        {"role": "user", "content": "Напиши пост для Telegram канала на основе этих новостей: " + titles}
    ])

def scan_and_consult(chat):
    send(chat, "🔍 <b>Агент 1</b> ищет свежие новости...")
    news = get_news()
    if not news:
        send(chat, "❌ Новостей не найдено")
        return
    msg = "📰 <b>Агент 1 нашёл:</b>\n\n"
    for i, n in enumerate(news):
        msg += str(i+1) + ". " + n["title"] + "\n📌 " + n["source"] + "\n\n"
    send(chat, msg)
    send(chat, "✍️ <b>Агент 3</b> пишет пост и генерирует картинку...")
    post = write_post(news)
    img_prompt = get_image_prompt(news)
    img_url = generate_image(img_prompt)
    pid = str(int(time.time()))
    pending[pid] = {"post": post, "news": news, "img": img_url}
    markup = {"inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
        {"text": "❌ Отклонить", "callback_data": "no_" + pid},
        {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
        {"text": "🖼 Новое фото", "callback_data": "newimg_" + pid}
    ]]}
    if img_url:
        send_photo(chat, img_url, "📝 <b>Готовый пост:</b>\n\n" + post + "\n\n─────────────\n<b>Агент 2</b> спрашивает: публиковать?", markup)
    else:
        send(chat, "📝 <b>Готовый пост:</b>\n\n" + post + "\n\n─────────────\nПубликовать?", markup)

def publish(chat, post, img_url=None):
    if img_url:
        send_photo(CHANNEL, img_url, post)
        send_photo(chat, img_url, "✅ <b>Пост с фото опубликован в</b> @cryptoainovosti!")
    else:
        send(CHANNEL, post)
        send(chat, "✅ <b>Пост опубликован в</b> @cryptoainovosti!")

def assistant(chat, text):
    if chat not in chat_history:
        chat_history[chat] = []
    chat_history[chat].append({"role": "user", "content": text})
    if len(chat_history[chat]) > 10:
        chat_history[chat] = chat_history[chat][-10:]
    system = """Ты главный AI ассистент крипто бота My Crypto Signals.
Ты управляешь командой из 4 агентов:
- Агент 1: ищет новости на CoinDesk, CoinTelegraph, Decrypt
- Агент 2: консультирует и спрашивает одобрение
- Агент 3: пишет посты и генерирует картинки
- Агент 4: публикует посты в канал @cryptoainovosti

Ты можешь отвечать на вопросы про крипто, объяснять рынок, давать советы.
Отвечай на русском языке, используй эмодзи. Будь дружелюбным и профессиональным."""
    messages = [{"role": "system", "content": system}] + chat_history[chat]
    response = ai(messages)
    chat_history[chat].append({"role": "assistant", "content": response})
    send(chat, "🤖 " + response)

def handle_callback(cb):
    data = cb["data"]
    chat = str(cb["message"]["chat"]["id"])
    try:
        requests.post(API + "/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=10)
    except:
        pass
    if data.startswith("ok_"):
        pid = data[3:]
        if pid in pending:
            publish(chat, pending[pid]["post"], pending[pid].get("img"))
            del pending[pid]
    elif data.startswith("no_"):
        pid = data[3:]
        if pid in pending:
            del pending[pid]
        send(chat, "❌ Пост отклонён")
    elif data.startswith("redo_"):
        pid = data[5:]
        send(chat, "🔄 Переписываю пост...")
        news = pending.get(pid, {}).get("news", get_news())
        post = write_post(news)
        img_url = pending.get(pid, {}).get("img")
        pending[pid] = {"post": post, "news": news, "img": img_url}
        markup = {"inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
            {"text": "❌ Отклонить", "callback_data": "no_" + pid},
            {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
            {"text": "🖼 Новое фото", "callback_data": "newimg_" + pid}
        ]]}
        if img_url:
            send_photo(chat, img_url, "📝 <b>Новый вариант:</b>\n\n" + post + "\n\n─────────────\nПубликовать?", markup)
        else:
            send(chat, "📝 <b>Новый вариант:</b>\n\n" + post + "\n\n─────────────\nПубликовать?", markup)
    elif data.startswith("newimg_"):
        pid = data[7:]
        send(chat, "🖼 Генерирую новую картинку...")
        news = pending.get(pid, {}).get("news", [])
        img_prompt = get_image_prompt(news)
        img_url = generate_image(img_prompt + " " + str(int(time.time())))
        if pid in pending:
            pending[pid]["img"] = img_url
        post = pending.get(pid, {}).get("post", "")
        markup = {"inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
            {"text": "❌ Отклонить", "callback_data": "no_" + pid},
            {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
            {"text": "🖼 Новое фото", "callback_data": "newimg_" + pid}
        ]]}
        if img_url:
            send_photo(chat, img_url, "🖼 <b>Новая картинка!</b>\n\n" + post, markup)

def auto_post():
    while True:
        if settings["auto"]:
            now = datetime.now()
            if now.hour == 9 and now.minute == 0:
                scan_and_consult(CHAT_ID)
        time.sleep(60)

def handle(msg):
    chat = str(msg["chat"]["id"])
    text = msg.get("text", "")
    if not text:
        return
    if text == "/start":
        send(chat,
            "👋 <b>Crypto AI Bot</b>\n\n"
            "🤖 Я твой главный AI ассистент!\n\n"
            "Агенты:\n"
            "🔍 Агент 1 — ищет свежие новости\n"
            "🤝 Агент 2 — консультирует тебя\n"
            "✍️ Агент 3 — пишет посты + генерирует фото\n"
            "📢 Агент 4 — публикует в канал\n\n"
            "Команды:\n"
            "/scan — найти новости и написать пост с фото\n"
            "/news — только новости\n"
            "/auto — автопост каждый день в 9:00\n"
            "/stop — выключить автопост\n"
            "/settings — настройки\n\n"
            "💬 Или просто напиши мне что угодно!"
        )
    elif text == "/scan":
        scan_and_consult(chat)
    elif text == "/news":
        send(chat, "🔍 Ищу свежие новости...")
        news = get_news()
        msg2 = "📰 <b>Топ новости:</b>\n\n"
        for i, n in enumerate(news):
            msg2 += str(i+1) + ". " + n["title"] + "\n📌 " + n["source"] + "\n\n"
        send(chat, msg2)
    elif text == "/auto":
        settings["auto"] = True
        send(chat, "✅ Автопост включён! Каждый день в 9:00")
    elif text == "/stop":
        settings["auto"] = False
        send(chat, "⏹ Автопост выключен")
    elif text == "/settings":
        send(chat,
            "⚙️ <b>Настройки:</b>\n\n"
            "Автопост: " + ("✅ Вкл" if settings["auto"] else "❌ Выкл") + "\n\n"
            "Просто напиши мне чтобы изменить!\n"
            "Например: 'включи автопост' или 'найди новости про биткоин'"
        )
    else:
        assistant(chat, text)

threading.Thread(target=auto_post, daemon=True).start()
send(CHAT_ID, "✅ <b>Crypto AI Bot запущен!</b>\n\n🤖 Все 4 агента готовы!\n🖼 Генерация фото включена!\nНапиши /start для начала.")

offset = 0
print("Бот запущен!")
while True:
    try:
        r = requests.get(API + "/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
        for u in r.json().get("result", []):
            offset = u["update_id"] + 1
            if "message" in u:
                handle(u["message"])
            elif "callback_query" in u:
                handle_callback(u["callback_query"])
    except Exception as e:
        print("Ошибка:", e)
    time.sleep(1)
