import requests
import time
from datetime import datetime
import json

TOKEN = "7993885857:AAHN-bMfGYUM2LlVBTBtwvQ6ECWPJNhQgmU"
CHAT_ID = "6923102781"

SYMBOLS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "ADA-USDT", "DOGE-USDT", "AVAX-USDT", "DOT-USDT", "LINK-USDT"
]

SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink"
}

def get_klines(symbol):
    url = f"https://api.kucoin.com/api/v1/market/candles?type=5min&symbol={symbol}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = list(reversed(res.json()["data"]))
        closes = [float(x[2]) for x in data]
        highs  = [float(x[3]) for x in data]
        lows   = [float(x[4]) for x in data]
        opens  = [float(x[1]) for x in data]
        print(f"✅ داده دریافت شد. تعداد کندل: {len(closes)}")
        return closes, highs, lows, opens
    except Exception as e:
        print(f"❌ خطا در دریافت داده: {symbol} -> {e}")
        return [], [], [], []

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period if sum(losses) else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_ma(closes, period=10):
    return sum(closes[-period:]) / period if len(closes) >= period else None

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1: return None
    trs = []
    for i in range(-period, 0):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return sum(trs) / period

def fetch_fundamental(symbol):
    try:
        coin_id = SYMBOL_MAP.get(symbol.split("-")[0], "bitcoin")
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        res = requests.get(url)
        data = res.json()
        rank = data.get("market_cap_rank", 999)
        marketcap = data.get("market_data", {}).get("market_cap", {}).get("usd", 0)
        return rank, marketcap
    except Exception as e:
        print(f"❌ خطا در فاندامنتال {symbol}: {e}")
        return None, None

def send_signal(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })

def send_chart_url(closes, symbol):
    if len(closes) < 20: return
    chart_config = {
        "type": "line",
        "data": {
            "labels": list(range(len(closes[-30:]))),
            "datasets": [{
                "label": symbol,
                "data": closes[-30:],
                "borderColor": "blue"
            }]
        },
        "options": {"title": {"display": True, "text": f"{symbol} Chart"}}
    }
    url = "https://quickchart.io/chart"
    full_url = requests.Request('GET', url, params={"c": json.dumps(chart_config)}).prepare().url
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data={
        "chat_id": CHAT_ID,
        "photo": full_url
    })

def classify_signal(rsi, ma10, price, last_open, last_close, prev_close, atr, rank):
    score = 0
    if rsi < 30 or rsi > 70: score += 1
    if (rsi < 30 and price > ma10) or (rsi > 70 and price < ma10): score += 1
    if abs(last_close - last_open) > abs(prev_close - last_close): score += 1
    if rank and rank <= 20: score += 1
    return score

def analyze(symbol):
    closes, highs, lows, opens = get_klines(symbol)
    if not closes: return

    price = closes[-1]
    rsi = calc_rsi(closes)
    ma10 = calc_ma(closes)
    atr = calc_atr(highs, lows, closes)
    rank, marketcap = fetch_fundamental(symbol)

    if None in (rsi, ma10, atr): return

    last_open, last_close = opens[-1], closes[-1]
    prev_close = closes[-2]

    score = classify_signal(rsi, ma10, price, last_open, last_close, prev_close, atr, rank)

    if score >= 4:
        level = "🟢 *سیگنال سطح ۳ - بسیار مطمئن*"
    elif score == 3:
        level = "🟡 *سیگنال سطح ۲ - با دقت متوسط*"
    elif score == 2:
        level = "🔵 *سیگنال سطح ۱ - کم‌ریسک*"
    else:
        print(f"⛔ سیگنال ضعیف برای {symbol}")
        return

    tp = round(price + 2 * atr, 4) if rsi < 50 else round(price - 2 * atr, 4)
    sl = round(price - atr, 4) if rsi < 50 else round(price + atr, 4)

    msg = f"""{level}
🪙 *{symbol}*
🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}
💰 *قیمت:* `{price}`
📉 *RSI:* `{round(rsi, 2)}`
📊 *MA10:* `{round(ma10, 2)}`
📐 *ATR:* `{round(atr, 4)}`
🎯 *TP:* `{tp}`
🛑 *SL:* `{sl}`
📊 *رتبه فاندامنتال:* `{rank}`"""
    send_signal(msg)
    send_chart_url(closes, symbol)

# اجرای مداوم
while True:
    print(f"\n⏳ بررسی جدید: {datetime.now()}")
    for symbol in SYMBOLS:
        analyze(symbol)
        time.sleep(1)
    time.sleep(300)  # 5 دقیقه
