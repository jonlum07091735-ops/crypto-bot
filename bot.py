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

# Тематические фото по категориям — реальные Unsplash фото по конкретным темам
THEMED_PHOTOS = {
    "bitcoin": [
        "https://images.unsplash.com/photo-1518544801976-3e159e50e5bb?w=1024&q=80",
        "https://images.unsplash.com/photo-1561622539-a6fe1b7e3ab6?w=1024&q=80",
        "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?w=1024&q=80",
        "https://images.unsplash.com/photo-1591994843349-f415893b3a6b?w=1024&q=80",
        "https://images.unsplash.com/photo-1629339942248-45d4b10c8c2f?w=1024&q=80",
        "https://images.unsplash.com/photo-1609554496796-c345a5335ceb?w=1024&q=80",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1024&q=80",
        "https://images.unsplash.com/photo-1640340434855-6084b1f4901c?w=1024&q=80",
    ],
    "ethereum": [
        "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=1024&q=80",
        "https://images.unsplash.com/photo-1622630998477-20aa696ecb05?w=1024&q=80",
        "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=1024&q=80",
        "https://images.unsplash.com/photo-1643101681604-f98a4b57b9f3?w=1024&q=80",
        "https://images.unsplash.com/photo-1644143379190-08a5f055de1d?w=1024&q=80",
        "https://images.unsplash.com/photo-1645731904636-24bb2c4b1e5f?w=1024&q=80",
    ],
    "trading": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1024&q=80",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1024&q=80",
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1024&q=80",
        "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?w=1024&q=80",
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1024&q=80",
        "https://images.unsplash.com/photo-1563986768494-4dee2763ff3f?w=1024&q=80",
        "https://images.unsplash.com/photo-1569025743873-ea3a9ade89f9?w=1024&q=80",
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=1024&q=80",
    ],
    "bull": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1024&q=80",
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=1024&q=80",
        "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?w=1024&q=80",
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1024&q=80",
        "https://images.unsplash.com/photo-1642790106117-e829e14a795f?w=1024&q=80",
        "https://images.unsplash.com/photo-1620321023374-d1a68fbc720d?w=1024&q=80",
    ],
    "bear": [
        "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?w=1024&q=80",
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1024&q=80",
        "https://images.unsplash.com/photo-1607863680198-23d4b2565df0?w=1024&q=80",
        "https://images.unsplash.com/photo-1508514177221-188b1cf16e9d?w=1024&q=80",
        "https://images.unsplash.com/photo-1574607383476-f517f260d30b?w=1024&q=80",
    ],
    "oil": [
        "https://images.unsplash.com/photo-1498354178607-a79df2916198?w=1024&q=80",
        "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=1024&q=80",
        "https://images.unsplash.com/photo-1611270629569-8b357cb88da9?w=1024&q=80",
        "https://images.unsplash.com/photo-1535637603896-07c179d71103?w=1024&q=80",
        "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?w=1024&q=80",
    ],
    "regulation": [
        "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1024&q=80",
        "https://images.unsplash.com/photo-1554469384-e58fac16e23a?w=1024&q=80",
        "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=1024&q=80",
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=1024&q=80",
    ],
    "defi": [
        "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=1024&q=80",
        "https://images.unsplash.com/photo-1644143379190-08a5f055de1d?w=1024&q=80",
        "https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?w=1024&q=80",
        "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=1024&q=80",
    ],
    "nft": [
        "https://images.unsplash.com/photo-1645378999496-33700b60e62d?w=1024&q=80",
        "https://images.unsplash.com/photo-1646803194571-e8e2a1c8e21d?w=1024&q=80",
        "https://images.unsplash.com/photo-1647427060118-4911c9821b82?w=1024&q=80",
        "https://images.unsplash.com/photo-1648318513261-c37ea6e7b8aa?w=1024&q=80",
    ],
    "analyst": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1024&q=80",
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1024&q=80",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1024&q=80",
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=1024&q=80",
        "https://images.unsplash.com/photo-1563986768494-4dee2763ff3f?w=1024&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1605792657660-596af9009e82?w=1024&q=80",
        "https://images.unsplash.com/photo-1592483648228-b35146a4330c?w=1024&q=80",
        "https://images.unsplash.com/photo-1630926854574-977b8e04c58c?w=1024&q=80",
        "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=1024&q=80",
        "https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?w=1024&q=80",
        "https://images.unsplash.com/photo-1569025743873-ea3a9ade89f9?w=1024&q=80",
        "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?w=1024&q=80",
        "https://images.unsplash.com/photo-1607863680198-23d4b2565df0?w=1024&q=80",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1024&q=80",
        "https://images.unsplash.com/photo-1620321023374-d1a68fbc720d?w=1024&q=80",
    ]
}

used_photos = {}

def get_image(title):
    t = title.lower()
    if "bitcoin" in t or "btc" in t:
        category = "bitcoin"
    elif "ethereum" in t or "eth" in t:
        category = "ethereum"
    elif "oil" in t or "нефть" in t or "brent" in t or "crude" in t:
        category = "oil"
    elif "nft" in t:
        category = "nft"
    elif "defi" in t or "decentralized" in t:
        category = "defi"
    elif "regulation" in t or "sec" in t or "ban" in t or "law" in t or "регул" in t:
        category = "regulation"
    elif "crash" in t or "drop" in t or "bear" in t or "падение" in t or "обвал" in t:
        category = "bear"
    elif "rally" in t or "surge" in t or "bull" in t or "ath" in t or "рост" in t:
        category = "bull"
    elif "analyst" in t or "forecast" in t or "аналитик" in t or "прогноз" in t:
        category = "analyst"
    elif "trading" in t or "trade" in t:
        category = "trading"
    else:
        category = "default"
    pool = THEMED_PHOTOS[category]
    if category not in used_photos:
        used_photos[category] = []
    available = [p for p in pool if p not in used_photos[category]]
    if not available:
        used_photos[category] = []
        available = pool
    img = random.choice(available)
    used_photos[category].append(img)
    return img

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
        for sym in ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]:
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
            code = valute.find("CharCode").text
            value = valute.find("Value").text.replace(",", ".")
            nominal = valute.find("Nominal").text
            if code in ["USD", "EUR"]:
                rates[code] = float(value) / float(nominal)
    except:
        pass
    return rates

def get_brent():
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
    brent = get_brent()
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
    text = format_rates()
    msg_id = send(CHANNEL, text)
    if msg_id:
        pinned_msg_id = msg_id
        pin_msg(CHANNEL, msg_id)
        print(f"Закреп создан: {msg_id}")
    while True:
        time.sleep(120)
        try:
            text = format_rates()
            if pinned_msg_id:
                ok = edit_msg(CHANNEL, pinned_msg_id, text)
                print(f"Курсы обновлены: {ok}")
                if not ok:
                    msg_id = send(CHANNEL, text)
                    if msg_id:
                        pinned_msg_id = msg_id
                        pin_msg(CHANNEL, msg_id)
            else:
                msg_id = send(CHANNEL, text)
                if msg_id:
                    pinned_msg_id = msg_id
                    pin_msg(CHANNEL, msg_id)
        except Exception as e:
            print("Ошибка курсов:", e)

def classify_news(title):
    t = title.lower()
    spam = ["sponsored", "advertisement", "casino", "gambling", "giveaway", "get rich"]
    for w in spam:
        if w in t:
            return None, 0
    bullish = ["rally", "surge", "bull", "growth", "adoption", "listing", "etf", "approval",
               "record", "ath", "rises", "gains", "soars", "jumps", "moon", "breakout",
               "рост", "ралли", "листинг", "одобрение", "рекорд", "растёт"]
    bearish = ["crash", "drop", "fall", "bear", "hack", "ban", "regulation", "sec",
               "lawsuit", "bankruptcy", "fraud", "decline", "plunges", "dump",
               "падение", "обвал", "взлом", "запрет", "банкротство", "падает"]
    analyst = ["analyst", "expert", "forecast", "prediction", "report", "research",
               "opinion", "analysis", "strategy", "аналитик", "прогноз", "мнение"]
    score = 0
    category = "neutral"
    for w in bullish:
        if w in t:
            score += 1
            category = "bull"
    for w in bearish:
        if w in t:
            score += 1
            if category != "bull":
                category = "bear"
    for w in analyst:
        if w in t:
            score += 1
            if category == "neutral":
                category = "analyst"
    return category, score

def normalize_title(title):
    return " ".join(title.lower().split()[:5])

def fetch_cryptopanic():
    news = []
    try:
        r = requests.get(
            "https://cryptopanic.com/api/v1/posts/?auth_token=public&kind=news&limit=20",
            timeout=10
        )
        for item in r.json().get("results", [])[:15]:
            title = item.get("title", "")
            url = item.get("url", "")
            if title and len(title) > 15:
                news.append({"title": title, "source": "CryptoPanic", "url": url, "lang": "en"})
    except Exception as e:
        print("CryptoPanic error:", e)
    return news

def fetch_rss(url, source, lang):
    news = []
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item")
        if not items:
            soup = BeautifulSoup(r.content, "html.parser")
            items = soup.find_all("item")
        for item in items[:5]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            if not title_tag:
                continue
            t = title_tag.get_text().strip()
            if not t or len(t) < 15:
                continue
            u = ""
            if link_tag:
                u = link_tag.get_text().strip() or link_tag.get("href", "")
            news.append({"title": t, "source": source, "url": u, "lang": lang})
    except Exception as e:
        print(f"RSS error {source}: {e}")
    return news

def fetch_site(url, source, lang, tags=["h2", "h3"]):
    news = []
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag_name in tags:
            for tag in soup.find_all(tag_name)[:8]:
                t = tag.get_text().strip()
                if 20 < len(t) < 200:
                    news.append({"title": t, "source": source, "url": url, "lang": lang})
    except Exception as e:
        print(f"Site error {source}: {e}")
    return news

def fetch_oil_news():
    news = []
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search?q=oil+brent+price&newsCount=5",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        for item in r.json().get("news", [])[:5]:
            title = item.get("title", "")
            url = item.get("link", "")
            if title and len(title) > 15:
                news.append({"title": title, "source": "Yahoo Finance", "url": url, "lang": "en"})
    except Exception as e:
        print("Oil news error:", e)
    return news

def fetch_all_news():
    all_news = []
    all_news.extend(fetch_cryptopanic())
    all_news.extend(fetch_site("https://www.coindesk.com", "CoinDesk", "en", ["h4", "h3"]))
    all_news.extend(fetch_site("https://cointelegraph.com", "CoinTelegraph", "en", ["h2"]))
    all_news.extend(fetch_site("https://forklog.com", "ForkLog", "ru", ["h2", "h3"]))
    all_news.extend(fetch_site("https://bits.media", "Bits.Media", "ru", ["h2", "h3"]))
    all_news.extend(fetch_oil_news())
    rss_list = [
        ("https://decrypt.co/feed", "Decrypt", "en"),
        ("https://u.today/rss", "U.Today", "en"),
        ("https://beincrypto.com/feed/", "BeInCrypto", "en"),
        ("https://cryptopotato.com/feed/", "CryptoPotato", "en"),
        ("https://news.bitcoin.com/feed/", "Bitcoin.com", "en"),
        ("https://ambcrypto.com/feed/", "AMBCrypto", "en"),
        ("https://incrypted.com/feed/", "Incrypted", "ru"),
        ("https://medium.com/feed/tag/bitcoin", "Medium Bitcoin", "en"),
        ("https://medium.com/feed/tag/cryptocurrency", "Medium Crypto", "en"),
        ("https://medium.com/feed/tag/trading", "Medium Trading", "en"),
    ]
    for url, source, lang in rss_list:
        all_news.extend(fetch_rss(url, source, lang))
    seen_titles = set()
    unique = []
    for item in all_news:
        nid = hashlib.md5(item["title"].encode()).hexdigest()
        norm = normalize_title(item["title"])
        if nid not in seen_news and norm not in seen_titles:
            seen_titles.add(norm)
            category, score = classify_news(item["title"])
            if category is not None:
                item["category"] = category
                item["score"] = score
                item["id"] = nid
                unique.append(item)
    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique

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

def write_post(title, source, article_text="", lang="en"):
    if article_text:
        content = f"Заголовок: {title}\nИсточник: {source}\n\nТекст:\n{article_text}"
    else:
        content = f"Заголовок: {title}\nИсточник: {source}"
    system = "Ты крипто эксперт и автор Telegram канала @cryptoainovosti."
    if lang == "en":
        system += " Переведи с английского и напиши интересный пост на русском."
    else:
        system += " Напиши интересный пост на русском языке."
    system += " Используй эмодзи. 150-200 слов. Укажи источник в конце."
    return ai([
        {"role": "system", "content": system},
        {"role": "user", "content": content}
    ])

def prepare_and_send(chat, item):
    title = item["title"]
    source = item["source"]
    url = item.get("url", "")
    lang = item.get("lang", "en")
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
    post = write_post(title, source, article_text, lang)
    img_url = get_image(title)
    pid = str(int(time.time()))
    pending[pid] = {"post": post, "img": img_url, "title": title, "category": category}
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
                print(f"Новых новостей: {new_count}")
            except Exception as e:
                print("Ошибка мониторинга:", e)
        time.sleep(1800)

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
        post = write_post(title, "", "", "en")
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
    elif data == "update_rates":
        text_rates = format_rates()
        if pinned_msg_id:
            ok = edit_msg(CHANNEL, pinned_msg_id, text_rates)
            if ok:
                send(chat, "✅ Закреп в канале обновлён!")
            else:
                msg_id = send(CHANNEL, text_rates)
                if msg_id:
                    pinned_msg_id = msg_id
                    pin_msg(CHANNEL, msg_id)
                    send(chat, "✅ Закреп обновлён!")
        else:
            msg_id = send(CHANNEL, text_rates)
            if msg_id:
                pinned_msg_id = msg_id
                pin_msg(CHANNEL, msg_id)
                send(chat, "✅ Закреп создан в канале!")
    elif data.startswith("newimg_"):
        pid = data[7:]
        title = pending.get(pid, {}).get("title", "crypto")
        new_img = get_image(title)
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
            "📡 Курсы в закрепе — каждые 2 минуты\n"
            "🖼 Тематические фото по теме новости\n"
            "🔄 Дубли исключены\n\n"
            "📰 15+ источников новостей\n"
            "Команды:\n"
            "/monitor — мониторинг каждые 30 мин\n"
            "/stop — выключить\n"
            "/scan — разовая проверка\n"
            "/news — свежие новости\n"
            "/rates — курсы\n\n"
            "💬 Напиши мне что угодно!"
        )
    elif text == "/monitor":
        settings["auto_monitor"] = True
        seen_news.clear()
        send(chat, "✅ <b>Мониторинг включён!</b>\nПроверка каждые 30 минут")
    elif text == "/stop":
        settings["auto_monitor"] = False
        send(chat, "⏹ Мониторинг выключен")
    elif text == "/scan":
        send(chat, "🔍 Сканирую источники...")
        news = fetch_all_news()
        if news:
            prepare_and_send(chat, news[0])
        else:
            send(chat, "❌ Попробуй позже")
    elif text == "/news":
        send(chat, "🔍 Загружаю новости...")
        news = fetch_all_news()
        if not news:
            send(chat, "❌ Попробуй позже")
            return
        msg2 = "📰 <b>Свежие новости:</b>\n\n"
        for n in news[:10]:
            icon = "📈" if n["category"] == "bull" else "📉" if n["category"] == "bear" else "🔍" if n["category"] == "analyst" else "📰"
            flag = "🇷🇺" if n["lang"] == "ru" else "🇺🇸"
            priority = "🔴" if n["score"] >= 3 else "🟡"
            msg2 += f"{priority}{icon}{flag} {n['title']}\n📌 {n['source']}\n\n"
        send(chat, msg2)
    elif text == "/rates":
        text_rates = format_rates()
        markup = {"inline_keyboard": [[
            {"text": "🔄 Обновить закреп в канале", "callback_data": "update_rates"}
        ]]}
        send(chat, text_rates, markup)
    else:
        assistant(chat, text)

threading.Thread(target=rates_updater, daemon=True).start()
threading.Thread(target=monitor_news, daemon=True).start()

send(CHAT_ID,
    "✅ <b>Бот запущен!</b>\n"
    "📡 Курсы появятся в закрепе через 10 сек\n"
    "🖼 Тематические фото по теме новости\n"
    "Напиши /start"
)

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
