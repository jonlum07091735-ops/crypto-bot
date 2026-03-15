import os
import requests
import time
import threading
from datetime import datetime
from bs4 import BeautifulSoup
import urllib.parse
import hashlib

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
API = "https://api.telegram.org/bot" + TOKEN
CHANNEL = "@cryptoainovosti"

pending = {}
settings = {"auto_monitor": False}
chat_history = {}
seen_news = set()

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
        r = requests.post(API + "/sendPhoto", json=data, timeout=15)
        return r.json().get("ok", False)
    except:
        return False

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
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=512&nologo=true&seed={int(time.time())}"
        return url
    except:
        return None

def get_image_prompt(title):
    prompt = ai([
        {"role": "system", "content": "Generate a short English image prompt (max 15 words) for a crypto news illustration. Style: modern, digital, financial, dark background. No text."},
        {"role": "user", "content": "News: " + title}
    ])
    return prompt[:150]

def write_post(title, source):
    return ai([
        {"role": "system", "content": "Ты крипто эксперт и автор популярного Telegram канала @cryptoainovosti. Пиши интересные посты на русском. Используй эмодзи. 100-150 слов. В конце добавь источник."},
        {"role": "user", "content": f"Напиши пост для Telegram канала на основе новости:\n\nЗаголовок: {title}\nИсточник: {source}"}
    ])

def fetch_all_news():
    news = []

    # CryptoPanic — агрегатор всех крипто новостей
    try:
        r = requests.get(
            "https://cryptopanic.com/api/v1/posts/?auth_token=public&kind=news&limit=20",
            timeout=10
        )
        for i in r.json().get("results", [])[:10]:
            news.append({
                "title": i["title"],
                "source": "CryptoPanic",
                "id": hashlib.md5(i["title"].encode()).hexdigest()
            })
    except:
        pass

    # CoinDesk
    try:
        r = requests.get("https://coindesk.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup.find_all("h4")[:5]:
            text = t.get_text().strip()
            if len(text) > 20:
                news.append({
                    "title": text,
                    "source": "CoinDesk",
                    "id": hashlib.md5(text.encode()).hexdigest()
                })
    except:
        pass

    # CoinTelegraph
    try:
        r = requests.get("https://cointelegraph.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup.find_all("h2")[:5]:
            text = t.get_text().strip()
            if len(text) > 20:
                news.append({
                    "title": text,
                    "source": "CoinTelegraph",
                    "id": hashlib.md5(text.encode()).hexdigest()
                })
    except:
        pass

    # Decrypt
    try:
        r = requests.get("https://decrypt.co", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup.find_all("h3")[:5]:
            text = t.get_text().strip()
            if len(text) > 20:
                news.append({
                    "title": text,
                    "source": "Decrypt",
                    "id": hashlib.md5(text.encode()).hexdigest()
                })
    except:
        pass

    # Bitcoin Magazine
    try:
        r = requests.get("https://bitcoinmagazine.com", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup.find_all("h2")[:3]:
            text = t.get_text().strip()
            if len(text) > 20:
                news.append({
                    "title": text,
                    "source": "Bitcoin Magazine",
                    "id": hashlib.md5(text.encode()).hexdigest()
                })
    except:
        pass

    return news

def prepare_and_send(chat, item):
    title = item["title"]
    source = item["source"]
    send(chat, f"🔔 <b>Новая новость!</b>\n📌 {source}\n\n<i>{title}</i>\n\n✍️ Готовлю пост и фото...")
    post = write_post(title, source)
    img_prompt = get_image_prompt(title)
    img_url = generate_image(img_prompt)
    pid = str(int(time.time()))
    pending[pid] = {"post": post, "img": img_url, "title": title}
    markup = {"inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
        {"text": "❌ Отклонить", "callback_data": "no_" + pid},
        {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
        {"text": "🖼 Новое фото", "callback_data": "newimg_" + pid}
    ]]}
    caption = f"📝 <b>Готовый пост:</b>\n\n{post}\n\n─────────────\nПубликовать в @cryptoainovosti?"
    if img_url:
        ok = send_photo(chat, img_url, caption, markup)
        if not ok:
            send(chat, caption, markup)
    else:
        send(chat, caption, markup)

def monitor_news():
    while True:
        if settings["auto_monitor"]:
            try:
                all_news = fetch_all_news()
                for item in all_news:
                    if item["id"] not in seen_news:
                        seen_news.add(item["id"])
                        prepare_and_send(CHAT_ID, item)
                        time.sleep(5)
            except Exception as e:
                print("Ошибка мониторинга:", e)
        time.sleep(300)

def publish(chat, post, img_url=None):
    if img_url:
        ok = send_photo(CHANNEL, img_url, post)
        if ok:
            send(chat, "✅ <b>Пост с фото опубликован в</b> @cryptoainovosti!")
        else:
            send(CHANNEL, post)
            send(chat, "✅ <b>Пост опубликован в</b> @cryptoainovosti!")
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
Ты мониторишь новости с CryptoPanic, CoinDesk, CoinTelegraph, Decrypt, Bitcoin Magazine.
Как только появляется свежая новость — сразу генерируешь пост с фото и спрашиваешь одобрение.
Публикуешь в канал @cryptoainovosti.
Отвечай на русском языке, используй эмодзи."""
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
        title = pending.get(pid, {}).get("title", "crypto news")
        post = write_post(title, "")
        img_url = pending.get(pid, {}).get("img")
        pending[pid]["post"] = post
        markup = {"inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
            {"text": "❌ Отклонить", "callback_data": "no_" + pid},
            {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
            {"text": "🖼 Новое фото", "callback_data": "newimg_" + pid}
        ]]}
        caption = f"📝 <b>Новый вариант:</b>\n\n{post}\n\n─────────────\nПубликовать?"
        if img_url:
            send_photo(chat, img_url, caption, markup)
        else:
            send(chat, caption, markup)
    elif data.startswith("newimg_"):
        pid = data[7:]
        send(chat, "🖼 Генерирую новую картинку...")
        title = pending.get(pid, {}).get("title", "crypto")
        img_prompt = get_image_prompt(title)
        img_url = generate_image(img_prompt)
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

def handle(msg):
    chat = str(msg["chat"]["id"])
    text = msg.get("text", "")
    if not text:
        return
    if text == "/start":
        send(chat,
            "👋 <b>Crypto AI Bot</b>\n\n"
            "🤖 Я слежу за новостями 24/7!\n\n"
            "Источники:\n"
            "📌 CryptoPanic\n"
            "📌 CoinDesk\n"
            "📌 CoinTelegraph\n"
            "📌 Decrypt\n"
            "📌 Bitcoin Magazine\n\n"
            "Команды:\n"
            "/monitor — включить мониторинг новостей\n"
            "/stop — выключить мониторинг\n"
            "/scan — разовая проверка новостей\n"
            "/news — показать свежие новости\n"
            "/settings — настройки\n\n"
            "💬 Или просто напиши мне что угодно!"
        )
    elif text == "/monitor":
        settings["auto_monitor"] = True
        seen_news.clear()
        send(chat, "✅ <b>Мониторинг включён!</b>\n\n🔔 Буду присылать каждую свежую новость с готовым постом и фото!\nПроверка каждые 5 минут.")
    elif text == "/stop":
        settings["auto_monitor"] = False
        send(chat, "⏹ Мониторинг выключен")
    elif text == "/scan":
        send(chat, "🔍 Ищу свежие новости...")
        news = fetch_all_news()
        if news:
            prepare_and_send(chat, news[0])
        else:
            send(chat, "❌ Новостей не найдено")
    elif text == "/news":
        send(chat, "🔍 Ищу новости...")
        news = fetch_all_news()
        msg2 = "📰 <b>Свежие новости:</b>\n\n"
        for i, n in enumerate(news[:8]):
            msg2 += str(i+1) + ". " + n["title"] + "\n📌 " + n["source"] + "\n\n"
        send(chat, msg2)
    elif text == "/settings":
        send(chat,
            "⚙️ <b>Настройки:</b>\n\n"
            "Мониторинг: " + ("✅ Вкл" if settings["auto_monitor"] else "❌ Выкл") + "\n\n"
            "Источники: CryptoPanic, CoinDesk, CoinTelegraph, Decrypt, Bitcoin Magazine\n"
            "Интервал проверки: каждые 5 минут"
        )
    else:
        assistant(chat, text)

threading.Thread(target=monitor_news, daemon=True).start()
send(CHAT_ID, "✅ <b>Crypto AI Bot запущен!</b>\n\n🔔 Мониторинг новостей готов!\nНапиши /monitor чтобы начать получать свежие новости.")

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
