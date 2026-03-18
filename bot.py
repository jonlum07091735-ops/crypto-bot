import os
import requests
import time
import threading
from datetime import datetime
from bs4 import BeautifulSoup
import hashlib
import random
import xml.etree.ElementTree as ET

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
API = "https://api.telegram.org/bot" + TOKEN
CHANNEL = "@cryptoainovosti"

pending = {}
settings = {"auto_monitor": False}
chat_history = {}
seen_news = set()
pinned_msg_id = None

CRYPTO_IMAGES = [
    "https://images.unsplash.com/photo-1518544801976-3e159e50e5bb?w=1024",
    "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=1024",
    "https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?w=1024",
    "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=1024",
    "https://images.unsplash.com/photo-1605792657660-596af9009e82?w=1024",
    "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=1024",
    "https://images.unsplash.com/photo-1640340434855-6084b1f4901c?w=1024",
    "https://images.unsplash.com/photo-1630926854574-977b8e04c58c?w=1024",
]

RSS_SOURCES = [
    ("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"),
    ("https://cointelegraph.com/rss", "CoinTelegraph"),
    ("https://decrypt.co/feed", "Decrypt"),
    ("https://news.bitcoin.com/feed/", "Bitcoin.com"),
    ("https://cryptoslate.com/feed/", "CryptoSlate"),
    ("https://u.today/rss", "U.Today"),
    ("https://beincrypto.com/feed/", "BeInCrypto"),
    ("https://ambcrypto.com/feed/", "AMBCrypto"),
    ("https://cryptopotato.com/feed/", "CryptoPotato"),
    ("https://forklog.com/feed/", "ForkLog"),
    ("https://bits.media/rss/news/", "Bits.Media"),
    ("https://cryptopanic.com/news/rss/", "CryptoPanic"),
]

BULLISH_KEYWORDS = [
    "rally", "surge", "pump", "bull", "growth", "adoption", "partnership",
    "launch", "upgrade", "listing", "etf", "approval", "investment",
    "record", "all-time high", "ath", "breakthrough", "rises", "gains",
    "рост", "ралли", "инвестиции", "листинг", "одобрение", "партнёрство", "растёт"
]

BEARISH_KEYWORDS = [
    "crash", "drop", "fall", "bear", "hack", "exploit", "ban", "regulation",
    "sec", "lawsuit", "bankruptcy", "fraud", "decline", "sell-off", "plunges",
    "падение", "обвал", "взлом", "запрет", "регуляция", "банкротство", "падает"
]

ANALYST_KEYWORDS = [
    "analyst", "expert", "forecast", "prediction", "according to",
    "report", "research", "аналитик", "эксперт", "прогноз", "мнение"
]

SPAM_KEYWORDS = [
    "sponsored", "advertisement", "casino", "gambling", "giveaway", "get rich"
]

def get_image(title):
    t = title.lower()
    if "bitcoin" in t or "btc" in t:
        return CRYPTO_IMAGES[0]
    elif "ethereum" in t or "eth" in t:
        return CRYPTO_IMAGES[1]
    else:
        return random.choice(CRYPTO_IMAGES)

def send(chat, text, markup=None):
    data = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = markup
    try:
        r = requests.post(API + "/sendMessage", json=data, timeout=10)
        return r.json().get("result", {}).get("message_id")
    except:
        return None

def edit_msg(chat, msg_id, text):
    try:
        r = requests.post(API + "/editMessageText", json={
            "chat_id": chat, "message_id": msg_id,
            "text": text, "parse_mode": "HTML"
        }, timeout=10)
        return r.json().get("ok", False)
    except:
        return False

def pin_msg(chat, msg_id):
    try:
        requests.post(API + "/pinChatMessage", json={
            "chat_id": chat, "message_id": msg_id,
            "disable_notification": True
        }, timeout=10)
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
            json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 900},
            timeout=30
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "AI недоступен: " + str(e)

def get_crypto_prices():
    prices = {}
    try:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
        for sym in symbols:
            r = requests.get(
                "https://api.bybit.com/v5/market/tickers",
                params={"category": "spot", "symbol": sym},
                timeout=5
            )
            data = r.json().get("result", {}).get("list", [])
            if data:
                prices[sym] = {
                    "price": float(data[0].get("lastPrice", 0)),
                    "change": float(data[0].get("price24hPcnt", 0)) * 100
                }
    except:
        pass
    return prices

def get_cbr_rates():
    rates = {}
    try:
        r = requests.get("https://www.cbr.ru/scripts/XML_daily.asp", timeout=10)
        root = ET.fromstring(r.content)
        for valute in root.findall("Valute"):
            char_code = valute.find("CharCode").text
            value = valute.find("Value").text.replace(",", ".")
            nominal = valute.find("Nominal").text
            if char_code in ["USD", "EUR"]:
                rates[char_code] = float(value) / float(nominal)
    except:
        pass
    return rates

def get_brent_price():
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = r.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        prev = data["chart"]["result"][0]["meta"]["previousClose"]
        change = ((price - prev) / prev) * 100
        return {"price": price, "change": change}
    except:
        return None

def arrow(change):
    return "↑" if change >= 0 else "↓"

def format_rates():
    crypto = get_crypto_prices()
    cbr = get_cbr_rates()
    brent = get_brent_price()
    now = datetime.now().strftime("%d.%m.%Y · %H:%M")
    lines = [
        "╔════════════════════╗",
        "         📡 LIVE RATES",
        "╚════════════════════╝\n"
    ]
    for sym, label in [
        ("BTCUSDT", "🟡 BTC"),
        ("ETHUSDT", "🔵 ETH"),
        ("BNBUSDT", "🟠 BNB"),
        ("SOLUSDT", "🟣 SOL"),
        ("XRPUSDT", "🔵 XRP"),
    ]:
        if sym in crypto:
            p = crypto[sym]["price"]
            c = crypto[sym]["change"]
            a = arrow(c)
            sign = "+" if c >= 0 else ""
            price_str = f"{p:,.2f}" if p > 1 else f"{p:.4f}"
            lines.append(f"{label}    ${price_str}   {a} {sign}{c:.1f}%")
    lines.append("\n─────────────────────")
    if "USD" in cbr:
        lines.append(f"💵 USD   {cbr['USD']:.2f} ₽")
    if "EUR" in cbr:
        lines.append(f"💶 EUR   {cbr['EUR']:.2f} ₽")
    if brent:
        p = brent["price"]
        c = brent["change"]
        a = arrow(c)
        sign = "+" if c >= 0 else ""
        lines.append(f"🛢 BRENT   ${p:.2f}   {a} {sign}{c:.1f}%")
    lines.append("\n─────────────────────")
    lines.append(f"🕐 {now}")
    lines.append(f"📌 @cryptoainovosti")
    return "\n".join(lines)

def rates_updater():
    global pinned_msg_id
    time.sleep(10)
    while True:
        try:
            text = format_rates()
            if pinned_msg_id:
                ok = edit_msg(CHANNEL, pinned_msg_id, text)
                if not ok:
                    msg_id = send(CHANNEL, text)
                    if msg_id:
                        pinned_msg_id = msg_id
                        pin_msg(CHANNEL, msg_id)
                        print(f"Новый закреп: {msg_id}")
            else:
                msg_id = send(CHANNEL, text)
                if msg_id:
                    pinned_msg_id = msg_id
                    pin_msg(CHANNEL, msg_id)
                    print(f"Курсы закреплены: {msg_id}")
        except Exception as e:
            print("Ошибка курсов:", e)
        time.sleep(60)

def classify_news(title):
    t = title.lower()
    for w in SPAM_KEYWORDS:
        if w in t:
            return None, 0
    score = 0
    category = "neutral"
    for w in BULLISH_KEYWORDS:
        if w in t:
            score += 1
            category = "bull"
    for w in BEARISH_KEYWORDS:
        if w in t:
            score += 1
            category = "bear"
    for w in ANALYST_KEYWORDS:
        if w in t:
            score += 1
            if category == "neutral":
                category = "analyst"
    return category, score

def fetch_article_text(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50])
        return text[:2000]
    except:
        return ""

def fetch_all_news():
    news = []
    for rss_url, source in RSS_SOURCES:
        try:
            r = requests.get(rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            soup = BeautifulSoup(r.content, "xml")
            items = soup.find_all("item")
            if not items:
                soup = BeautifulSoup(r.content, "html.parser")
                items = soup.find_all("item")
            for item in items[:4]:
                title_tag = item.find("title")
                link_tag = item.find("link")
                if not title_tag:
                    continue
                t = title_tag.get_text().strip()
                if not t or len(t) < 15:
                    continue
                u = ""
                if link_tag:
                    u = link_tag.get_text().strip()
                    if not u:
                        u = link_tag.get("href", "")
                category, score = classify_news(t)
                if category is not None:
                    news.append({
                        "title": t,
                        "source": source,
                        "url": u,
                        "category": category,
                        "score": score,
                        "id": hashlib.md5(t.encode()).hexdigest()
                    })
        except Exception as e:
            print(f"Ошибка {source}: {e}")
            continue
    news.sort(key=lambda x: x["score"], reverse=True)
    return news

def write_post(title, source, article_text=""):
    if article_text:
        content = f"Заголовок: {title}\nИсточник: {source}\n\nТекст:\n{article_text}"
    else:
        content = f"Заголовок: {title}\nИсточник: {source}"
    return ai([
        {"role": "system", "content": "Ты крипто эксперт канала @cryptoainovosti. Если текст на английском — переведи. Напиши интересный пост на русском. Используй эмодзи. 150-200 слов. Укажи источник в конце."},
        {"role": "user", "content": content}
    ])

def prepare_and_send(chat, item):
    title = item["title"]
    source = item["source"]
    url = item.get("url", "")
    category = item.get("category", "neutral")
    score = item.get("score", 0)
    if category == "bull":
        icon = "📈"
        label = "Потенциальный рост"
    elif category == "bear":
        icon = "📉"
        label = "Потенциальное падение"
    elif category == "analyst":
        icon = "🔍"
        label = "Мнение аналитика"
    else:
        icon = "📰"
        label = "Новость"
    priority = "🔴 Срочно" if score >= 3 else "🟡 Важно"
    send(chat, f"{priority} | {icon} <b>{label}</b>\n📌 {source}\n\n<i>{title}</i>\n\n✍️ Готовлю пост...")
    article_text = fetch_article_text(url) if url else ""
    post = write_post(title, source, article_text)
    img_url = get_image(title)
    pid = str(int(time.time()))
    pending[pid] = {"post": post, "img": img_url, "title": title}
    markup = {"inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
        {"text": "❌ Отклонить", "callback_data": "no_" + pid},
        {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
        {"text": "🖼 Другое фото", "callback_data": "newimg_" + pid}
    ]]}
    caption = f"📝 <b>Готовый пост:</b>\n\n{post}\n\n─────────────\nПубликовать в @cryptoainovosti?"
    ok = send_photo(chat, img_url, caption, markup)
    if not ok:
        send(chat, caption, markup)

def publish(chat, post, img_url=None):
    if img_url:
        ok = send_photo(CHANNEL, img_url, post)
        if ok:
            send(chat, "✅ Пост с фото опубликован в @cryptoainovosti!")
            return
    send(CHANNEL, post)
    send(chat, "✅ Пост опубликован в @cryptoainovosti!")

def assistant(chat, text):
    if chat not in chat_history:
        chat_history[chat] = []
    chat_history[chat].append({"role": "user", "content": text})
    if len(chat_history[chat]) > 10:
        chat_history[chat] = chat_history[chat][-10:]
    system = "Ты главный AI ассистент крипто канала @cryptoainovosti. Отвечай на русском, используй эмодзи."
    messages = [{"role": "system", "content": system}] + chat_history[chat]
    response = ai(messages)
    chat_history[chat].append({"role": "assistant", "content": response})
    send(chat, "🤖 " + response)

def monitor_news():
    while True:
        if settings["auto_monitor"]:
            try:
                all_news = fetch_all_news()
                new_count = 0
                for item in all_news:
                    if item["id"] not in seen_news:
                        seen_news.add(item["id"])
                        prepare_and_send(CHAT_ID, item)
                        new_count += 1
                        time.sleep(20)
                        if new_count >= 5:
                            break
                if new_count == 0:
                    print("Новых новостей нет")
            except Exception as e:
                print("Ошибка мониторинга:", e)
        time.sleep(300)

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
        send(chat, "🔄 Переписываю...")
        title = pending.get(pid, {}).get("title", "crypto")
        post = write_post(title, "", "")
        img_url = pending.get(pid, {}).get("img")
        if pid in pending:
            pending[pid]["post"] = post
        markup = {"inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
            {"text": "❌ Отклонить", "callback_data": "no_" + pid},
            {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
            {"text": "🖼 Другое фото", "callback_data": "newimg_" + pid}
        ]]}
        caption = f"📝 <b>Новый вариант:</b>\n\n{post}\n\n─────────────\nПубликовать?"
        ok = send_photo(chat, img_url, caption, markup)
        if not ok:
            send(chat, caption, markup)
    elif data.startswith("newimg_"):
        pid = data[7:]
        new_img = random.choice(CRYPTO_IMAGES)
        if pid in pending:
            pending[pid]["img"] = new_img
        post = pending.get(pid, {}).get("post", "")
        markup = {"inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": "ok_" + pid},
            {"text": "❌ Отклонить", "callback_data": "no_" + pid},
            {"text": "🔄 Переписать", "callback_data": "redo_" + pid},
            {"text": "🖼 Другое фото", "callback_data": "newimg_" + pid}
        ]]}
        send_photo(chat, new_img, "🖼 <b>Другое фото!</b>\n\n" + post, markup)

def handle(msg):
    chat = str(msg["chat"]["id"])
    text = msg.get("text", "")
    if not text:
        return
    if text == "/start":
        send(chat,
            "👋 <b>Crypto AI Bot</b>\n\n"
            "📡 Курсы в канале — каждую минуту\n"
            "📰 12 источников новостей\n\n"
            "Команды:\n"
            "/monitor — мониторинг новостей\n"
            "/stop — выключить\n"
            "/scan — разовая проверка\n"
            "/news — свежие новости\n"
            "/rates — курсы\n\n"
            "💬 Или напиши мне что угодно!"
        )
    elif text == "/monitor":
        settings["auto_monitor"] = True
        seen_news.clear()
        send(chat, "✅ <b>Мониторинг включён!</b>\nПроверка каждые 5 минут · 12 источников")
    elif text == "/stop":
        settings["auto_monitor"] = False
        send(chat, "⏹ Мониторинг выключен")
    elif text == "/scan":
        send(chat, "🔍 Сканирую источники...")
        news = fetch_all_news()
        if news:
            prepare_and_send(chat, news[0])
        else:
            send(chat, "❌ Новостей не найдено — попробуй позже")
    elif text == "/news":
        send(chat, "🔍 Загружаю новости...")
        news = fetch_all_news()
        if not news:
            send(chat, "❌ Новостей не найдено — попробуй позже")
            return
        msg2 = "📰 <b>Свежие новости:</b>\n\n"
        for n in news[:10]:
            icon = "📈" if n["category"] == "bull" else "📉" if n["category"] == "bear" else "🔍" if n["category"] == "analyst" else "📰"
            priority = "🔴" if n["score"] >= 3 else "🟡"
            msg2 += f"{priority}{icon} {n['title']}\n📌 {n['source']}\n\n"
        send(chat, msg2)
    elif text == "/rates":
        send(chat, format_rates())
    else:
        assistant(chat, text)

threading.Thread(target=rates_updater, daemon=True).start()
threading.Thread(target=monitor_news, daemon=True).start()

send(CHAT_ID, "✅ <b>Бот запущен!</b>\n📡 Курсы появятся в канале через 10 сек\nНапиши /start")

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
