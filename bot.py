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
MAGIC_KEY = os.environ.get("MAGIC_HOUR_KEY")
API = "https://api.telegram.org/bot" + TOKEN
CHANNEL = "@cryptoainovosti"

pending = {}
settings = {"auto_monitor": False}
chat_history = {}
seen_news = set()
pinned_msg_id = None

def get_image(title):
    t = title.lower()
    if "bitcoin" in t or "btc" in t:
        query = "bitcoin cryptocurrency"
    elif "ethereum" in t or "eth" in t:
        query = "ethereum blockchain"
    elif "oil" in t or "нефть" in t or "brent" in t:
        query = "oil petroleum energy"
    elif "nft" in t:
        query = "nft digital art"
    elif "defi" in t:
        query = "defi blockchain finance"
    elif "regulation" in t or "sec" in t or "ban" in t:
        query = "law regulation finance"
    elif "crash" in t or "drop" in t or "bear" in t:
        query = "stock market crash finance"
    elif "rally" in t or "surge" in t or "bull" in t:
        query = "stock market growth bull"
    elif "analyst" in t or "forecast" in t:
        query = "financial analyst charts"
    elif "trading" in t:
        query = "trading charts finance"
    elif "solana" in t or "sol" in t:
        query = "solana crypto blockchain"
    elif "xrp" in t or "ripple" in t:
        query = "ripple xrp crypto"
    elif "bnb" in t or "binance" in t:
        query = "binance exchange crypto"
    else:
        query = "cryptocurrency blockchain finance"
    seed = random.randint(1, 99999)
    encoded = requests.utils.quote(query)
    return f"https://source.unsplash.com/1024x512/?{encoded}&sig={seed}"

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

def get_gif(title):
    try:
        t = title.lower()
        if "bitcoin" in t or "btc" in t:
            query = "bitcoin crypto"
        elif "ethereum" in t or "eth" in t:
            query = "ethereum crypto"
        elif "crash" in t or "drop" in t or "bear" in t:
            query = "stock market crash"
        elif "rally" in t or "surge" in t or "bull" in t:
            query = "bull market money"
        elif "oil" in t or "brent" in t:
            query = "oil energy"
        else:
            query = "cryptocurrency blockchain"
        r = requests.get(
            "https://api.giphy.com/v1/gifs/search",
            params={
                "api_key": "dc6zaTOxFJmzC",
                "q": query,
                "limit": 20,
                "rating": "g"
            },
            timeout=10
        )
        gifs = r.json().get("data", [])
        if gifs:
            gif = random.choice(gifs)
            return gif["images"]["original"]["url"]
        return None
    except Exception as e:
        print("Ошибка GIF:", e)
        return None

def send_animation(chat, gif_url, caption=""):
    try:
        r = requests.post(API + "/sendAnimation", json={
            "chat_id": chat,
            "animation": gif_url,
            "caption": caption,
            "parse_mode": "HTML"
        }, timeout=15)
        return r.json().get("ok", False)
    except:
        return False

def auto_gif():
    time.sleep(180)
    while True:
        try:
            news = fetch_all_news()
            for item in news:
                if item["id"] not in seen_news:
                    title = item["title"]
                    category = item.get("category", "neutral")
                    hashtags = get_hashtags(title, category)
                    gif_url = get_gif(title)
                    if gif_url:
                        caption = f"🎬 <b>{title[:150]}</b>\n\n@cryptoainovosti{hashtags}"
                        ok = send_animation(CHANNEL, gif_url, caption)
                        if ok:
                            send(CHAT_ID, f"✅ GIF опубликован:\n<i>{title}</i>")
                    break
        except Exception as e:
            print("Ошибка авто-GIF:", e)
        time.sleep(10800)

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
    lines = ["📡 <b>LIVE RATES</b>\n"]
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
            lines.append(f"{label}  ${price_str}  {a} {sign}{c:.1f}%")
    lines.append("")
    if "USD" in cbr:
        lines.append(f"💵 USD  {cbr['USD']:.2f} ₽")
    if "EUR" in cbr:
        lines.append(f"💶 EUR  {cbr['EUR']:.2f} ₽")
    if brent:
        p = brent["price"]
        c = brent["change"]
        a = arrow(c)
        sign = "+" if c >= 0 else ""
        lines.append(f"🛢 BRENT  ${p:.2f}  {a} {sign}{c:.1f}%")
    lines.append("\n🔄 <i>Данные обновляются каждые 60 секунд</i>")
    return "\n".join(lines)

def get_pinned_msg_id():
    try:
        r = requests.get(API + "/getChat", json={"chat_id": CHANNEL}, timeout=10)
        pinned = r.json().get("result", {}).get("pinned_message", {})
        return pinned.get("message_id")
    except:
        return None

def rates_updater():
    global pinned_msg_id
    time.sleep(15)
    pinned_msg_id = get_pinned_msg_id()
    print(f"Найден закреп: {pinned_msg_id}")
    if not pinned_msg_id:
        msg_id = send(CHANNEL, format_rates())
        if msg_id:
            pinned_msg_id = msg_id
            pin_msg(CHANNEL, msg_id)
            print(f"Закреп создан: {msg_id}")
    while True:
        try:
            text = format_rates()
            if pinned_msg_id:
                ok = edit_msg(CHANNEL, pinned_msg_id, text)
                print(f"Обновлено: {ok} id={pinned_msg_id}")
                if not ok:
                    pinned_msg_id = get_pinned_msg_id()
                    if not pinned_msg_id:
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
        time.sleep(60)

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

def get_top10_prices():
    top10 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
             "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT"]
    prices = {}
    try:
        for sym in top10:
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

def format_top10(prices):
    icons = {
        "BTCUSDT": "🟡", "ETHUSDT": "🔵", "BNBUSDT": "🟠",
        "SOLUSDT": "🟣", "XRPUSDT": "🔵", "ADAUSDT": "🔵",
        "DOGEUSDT": "🟡", "AVAXUSDT": "🔴", "DOTUSDT": "🔴",
        "MATICUSDT": "🟣"
    }
    names = {
        "BTCUSDT": "BTC", "ETHUSDT": "ETH", "BNBUSDT": "BNB",
        "SOLUSDT": "SOL", "XRPUSDT": "XRP", "ADAUSDT": "ADA",
        "DOGEUSDT": "DOGE", "AVAXUSDT": "AVAX", "DOTUSDT": "DOT",
        "MATICUSDT": "MATIC"
    }
    lines = ["📊 <b>Топ 10 монет:</b>"]
    for sym, data in prices.items():
        p = data["price"]
        c = data["change"]
        a = "↑" if c >= 0 else "↓"
        sign = "+" if c >= 0 else ""
        price_str = f"{p:,.2f}" if p > 1 else f"{p:.4f}"
        icon = icons.get(sym, "⚪")
        name = names.get(sym, sym.replace("USDT", ""))
        lines.append(f"{icon} {name}: ${price_str} {a} {sign}{c:.1f}%")
    return "\n".join(lines)

def get_top_movers():
    try:
        r = requests.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "spot"},
            timeout=10
        )
        tickers = r.json().get("result", {}).get("list", [])
        movers = []
        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            try:
                price = float(t.get("lastPrice", 0))
                change = float(t.get("price24hPcnt", 0)) * 100
                volume = float(t.get("turnover24h", 0))
                if volume > 1000000 and price > 0:
                    movers.append({"symbol": sym.replace("USDT", ""), "price": price, "change": change, "volume": volume})
            except:
                continue
        gainers = sorted(movers, key=lambda x: x["change"], reverse=True)[:3]
        losers = sorted(movers, key=lambda x: x["change"])[:3]
        return gainers, losers
    except:
        return [], []

def format_movers(gainers, losers):
    text = ""
    if gainers:
        text += "🚀 <b>Топ роста за 24ч:</b>\n"
        for m in gainers:
            text += f"  🟢 {m['symbol']}: ${m['price']:,.4f} ↑ +{m['change']:.1f}%\n"
    if losers:
        text += "\n💀 <b>Топ падения за 24ч:</b>\n"
        for m in losers:
            text += f"  🔴 {m['symbol']}: ${m['price']:,.4f} ↓ {m['change']:.1f}%\n"
    return text

def send_poll(question, options):
    try:
        requests.post(API + "/sendPoll", json={
            "chat_id": CHANNEL,
            "question": question,
            "options": options,
            "is_anonymous": True
        }, timeout=10)
    except:
        pass

def morning_review():
    crypto = get_crypto_prices()
    top10 = get_top10_prices()
    gainers, losers = get_top_movers()
    btc = crypto.get("BTCUSDT", {})
    eth = crypto.get("ETHUSDT", {})
    sol = crypto.get("SOLUSDT", {})
    btc_p = btc.get("price", 0)
    btc_c = btc.get("change", 0)
    eth_p = eth.get("price", 0)
    eth_c = eth.get("change", 0)
    sol_p = sol.get("price", 0)
    sol_c = sol.get("change", 0)
    now = datetime.now().strftime("%d.%m.%Y")
    gainers_text = ", ".join([f"{m['symbol']} +{m['change']:.1f}%" for m in gainers])
    losers_text = ", ".join([f"{m['symbol']} {m['change']:.1f}%" for m in losers])
    review = ai([
        {"role": "system", "content": "Ты крипто аналитик канала @cryptoainovosti. Напиши утренний обзор рынка на русском. Используй эмодзи. 180-220 слов. Упомяни топ монеты роста и падения. Дай прогноз на день."},
        {"role": "user", "content": f"Данные на {now}:\nBTC: ${btc_p:,.0f} ({'+' if btc_c >= 0 else ''}{btc_c:.1f}%)\nETH: ${eth_p:,.0f} ({'+' if eth_c >= 0 else ''}{eth_c:.1f}%)\nSOL: ${sol_p:.2f} ({'+' if sol_c >= 0 else ''}{sol_c:.1f}%)\nТоп роста: {gainers_text}\nТоп падения: {losers_text}"}
    ])
    top10_text = format_top10(top10)
    movers_text = format_movers(gainers, losers)
    img = get_image("trading bull market morning analysis")
    caption = f"🌅 <b>Утренний обзор рынка</b>\n📅 {now}\n\n{review}\n\n{top10_text}\n\n{movers_text}"
    send_photo(CHANNEL, img, caption)
    time.sleep(3)
    if gainers:
        top_gainer = gainers[0]["symbol"]
        send_poll(
            f"📊 {top_gainer} вырос на {gainers[0]['change']:.1f}% за ночь. Что думаешь?",
            ["🚀 Продолжит рост", "📉 Скоро откат", "🤷 Не знаю"]
        )
    else:
        send_poll(
            "📊 Как думаешь, куда пойдёт BTC сегодня?",
            ["📈 Вырастет", "📉 Упадёт", "➡️ Будет боковик"]
        )

def evening_summary():
    crypto = get_crypto_prices()
    top10 = get_top10_prices()
    gainers, losers = get_top_movers()
    btc = crypto.get("BTCUSDT", {})
    eth = crypto.get("ETHUSDT", {})
    bnb = crypto.get("BNBUSDT", {})
    sol = crypto.get("SOLUSDT", {})
    xrp = crypto.get("XRPUSDT", {})
    now = datetime.now().strftime("%d.%m.%Y")
    gainers_text = ", ".join([f"{m['symbol']} +{m['change']:.1f}%" for m in gainers])
    losers_text = ", ".join([f"{m['symbol']} {m['change']:.1f}%" for m in losers])
    summary = ai([
        {"role": "system", "content": "Ты крипто аналитик канала @cryptoainovosti. Напиши вечерние итоги дня на русском. Используй эмодзи. 180-220 слов. Упомяни топ монеты роста и падения за день. Дай прогноз на завтра."},
        {"role": "user", "content": f"Итоги {now}:\nBTC: ${btc.get('price',0):,.0f} ({'+' if btc.get('change',0) >= 0 else ''}{btc.get('change',0):.1f}%)\nETH: ${eth.get('price',0):,.0f} ({'+' if eth.get('change',0) >= 0 else ''}{eth.get('change',0):.1f}%)\nBNB: ${bnb.get('price',0):.0f}\nSOL: ${sol.get('price',0):.2f}\nXRP: ${xrp.get('price',0):.4f}\nТоп роста: {gainers_text}\nТоп падения: {losers_text}"}
    ])
    top10_text = format_top10(top10)
    movers_text = format_movers(gainers, losers)
    img = get_image("trading analysis evening results market")
    caption = f"🌙 <b>Итоги дня</b>\n📅 {now}\n\n{summary}\n\n{top10_text}\n\n{movers_text}"
    send_photo(CHANNEL, img, caption)
    time.sleep(3)
    send_poll(
        "🔮 Прогноз на завтра?",
        ["🟢 Рынок вырастет", "🔴 Рынок упадёт", "🟡 Без изменений", "🤷 Сложно сказать"]
    )

def daily_scheduler():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0:
            try:
                morning_review()
            except Exception as e:
                print("Ошибка утреннего обзора:", e)
        if now.hour == 20 and now.minute == 0:
            try:
                evening_summary()
            except Exception as e:
                print("Ошибка вечерних итогов:", e)
        time.sleep(60)

def get_hashtags(title, category):
    base = "#крипто #криптовалюта #crypto #bitcoin #биткоин #btc #трейдинг #криптоновости"
    t = title.lower()
    extra = ""
    if "bitcoin" in t or "btc" in t:
        extra = "#bitcoin #биткоин #btc #bitcoinnews"
    elif "ethereum" in t or "eth" in t:
        extra = "#ethereum #eth #эфириум"
    elif "solana" in t or "sol" in t:
        extra = "#solana #sol #соланa"
    elif "xrp" in t or "ripple" in t:
        extra = "#xrp #ripple #риппл"
    elif "bnb" in t or "binance" in t:
        extra = "#bnb #binance #байбит"
    elif "nft" in t:
        extra = "#nft #нфт #digitalart"
    elif "defi" in t:
        extra = "#defi #децентрализация #web3"
    elif "oil" in t or "нефть" in t or "brent" in t:
        extra = "#нефть #brent #сырьё #commodities"
    if category == "bull":
        extra += " #рост #bullmarket #лонг"
    elif category == "bear":
        extra += " #падение #bearmarket #шорт"
    elif category == "analyst":
        extra += " #аналитика #прогноз #анализрынка"
    return f"\n\n{base} {extra}".strip()

HASHTAGS = {
    "base": ["#крипто", "#криптовалюта", "#crypto", "#bitcoin", "#биткоин", "#трейдинг", "#криптоновости"],
    "bitcoin": ["#bitcoin", "#btc", "#биткоин", "#bitcoinnews"],
    "ethereum": ["#ethereum", "#eth", "#эфириум"],
    "bull": ["#рост", "#bullmarket", "#лонг", "#pump"],
    "bear": ["#падение", "#bearmarket", "#шорт", "#dump"],
    "analyst": ["#аналитика", "#прогноз", "#анализрынка"],
    "oil": ["#нефть", "#brent", "#сырьё"],
    "defi": ["#defi", "#web3", "#децентрализация"],
    "nft": ["#nft", "#нфт", "#digitalart"],
    "default": ["#altcoin", "#инвестиции", "#финансы", "#рынок"]
}

def update_hashtags():
    while True:
        try:
            trending = []
            r = requests.get(
                "https://cryptopanic.com/api/v1/posts/?auth_token=public&kind=news&limit=20",
                timeout=10
            )
            for item in r.json().get("results", [])[:20]:
                title = item.get("title", "").lower()
                words = title.split()
                for word in words:
                    if len(word) > 4 and word.isalpha():
                        trending.append("#" + word)
            if trending:
                from collections import Counter
                top = [tag for tag, _ in Counter(trending).most_common(5)]
                HASHTAGS["trending"] = top
                print(f"Хэштеги обновлены: {top}")
        except Exception as e:
            print("Ошибка обновления хэштегов:", e)
        time.sleep(86400)

def get_hashtags(title, category):
    t = title.lower()
    tags = list(HASHTAGS["base"])
    if "bitcoin" in t or "btc" in t:
        tags.extend(HASHTAGS["bitcoin"])
    elif "ethereum" in t or "eth" in t:
        tags.extend(HASHTAGS["ethereum"])
    elif "oil" in t or "нефть" in t or "brent" in t:
        tags.extend(HASHTAGS["oil"])
    elif "nft" in t:
        tags.extend(HASHTAGS["nft"])
    elif "defi" in t:
        tags.extend(HASHTAGS["defi"])
    else:
        tags.extend(HASHTAGS["default"])
    if category == "bull":
        tags.extend(HASHTAGS["bull"])
    elif category == "bear":
        tags.extend(HASHTAGS["bear"])
    elif category == "analyst":
        tags.extend(HASHTAGS["analyst"])
    if "trending" in HASHTAGS:
        tags.extend(HASHTAGS["trending"][:3])
    unique = list(dict.fromkeys(tags))
    return "\n\n" + " ".join(unique[:15])

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
    caption = f"📝 <b>Готовый пост:</b>\n\n{post}{get_hashtags(title, category)}\n\n─────────────\nПубликовать в @cryptoainovosti?"
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

def auto_publish():
    time.sleep(60)
    while True:
        try:
            news = fetch_all_news()
            for item in news:
                if item["id"] not in seen_news:
                    seen_news.add(item["id"])
                    title = item["title"]
                    source = item["source"]
                    url = item.get("url", "")
                    lang = item.get("lang", "en")
                    category = item.get("category", "neutral")
                    article_text = fetch_article_text(url) if url else ""
                    post = write_post(title, source, article_text, lang)
                    hashtags = get_hashtags(title, category)
                    img_url = get_image(title)
                    full_post = post + hashtags
                    ok = send_photo(CHANNEL, img_url, full_post)
                    if not ok:
                        send(CHANNEL, full_post)
                    send(CHAT_ID, f"✅ Автопост опубликован:\n\n<i>{title}</i>")
                    print(f"Автопост: {title}")
                    break
        except Exception as e:
            print("Ошибка автопоста:", e)
        time.sleep(10800)

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
    elif data == "pub_gif":
        send(chat, "🔍 Ищу GIF...")
        news = fetch_all_news()
        if news:
            item = news[0]
            title = item["title"]
            category = item.get("category", "neutral")
            hashtags = get_hashtags(title, category)
            gif_url = get_gif(title)
            if gif_url:
                caption = f"🎬 <b>{title[:150]}</b>\n\n@cryptoainovosti{hashtags}"
                send_animation(CHANNEL, gif_url, caption)
                send(chat, "✅ GIF опубликован в канал!")
            else:
                send(chat, "❌ GIF не найден")
        else:
            send(chat, "❌ Новостей не найдено")
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
    elif text == "/gif":
        markup = {"inline_keyboard": [[
            {"text": "🎬 Опубликовать GIF в канал", "callback_data": "pub_gif"}
        ]]}
        send(chat, "🎬 Нажми кнопку чтобы опубликовать GIF по свежей новости!", markup)
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
threading.Thread(target=daily_scheduler, daemon=True).start()
threading.Thread(target=update_hashtags, daemon=True).start()
threading.Thread(target=auto_publish, daemon=True).start()
threading.Thread(target=auto_gif, daemon=True).start()

send(CHAT_ID,
    "✅ <b>Бот запущен!</b>\n"
    "📡 Курсы появятся в закрепе через 10 сек\n"
    "🌅 Утренний обзор в 9:00\n"
    "🌙 Вечерние итоги в 20:00\n"
    "🗳 Опросы после обзоров\n"
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
