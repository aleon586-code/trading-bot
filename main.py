import requests
import time
import pandas as pd
import json
import base64
import os
from datetime import datetime

PAIRS = ["EUR/USD"]
TD_API_KEY = os.environ.get("TD_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "aleon586-code/trading-bot"
GITHUB_FILE = "signal.json"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg})

def get_candles(pair):
    symbol = pair.replace("/", "")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=30&apikey={TD_API_KEY}"
    r = requests.get(url).json()
    df = pd.DataFrame(r["values"])
    df = df.rename(columns={"open":"open","high":"high","low":"low","close":"close"})
    for col in ["open","high","low","close"]:
        df[col] = df[col].astype(float)
    return df.iloc[::-1].reset_index(drop=True)

def analyze(pair):
    df = get_candles(pair)
    ema8 = df["close"].ewm(span=8).mean()
    ema21 = df["close"].ewm(span=21).mean()
    # ADX
    high = df["high"]
    low = df["low"]
    close = df["close"]
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=14).mean()
    plus_di = 100 * plus_dm.ewm(span=14).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=14).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(span=14).mean()
    last = -1
    prev = -2
    cross_up = ema8.iloc[prev] < ema21.iloc[prev] and ema8.iloc[last] > ema21.iloc[last]
    cross_dn = ema8.iloc[prev] > ema21.iloc[prev] and ema8.iloc[last] < ema21.iloc[last]
    strong = adx.iloc[last] > 30
    if cross_up and strong:
        return "CALL"
    if cross_dn and strong:
        return "PUT"
    return None

def write_signal(direction, pair):
    data = {"signal": {"direction": direction, "pair": pair, "time": int(time.time())}}
    content = base64.b64encode(json.dumps(data).encode()).decode()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    sha = requests.get(url, headers=headers).json().get("sha", "")
    requests.put(url, headers=headers, json={"message": "signal", "content": content, "sha": sha})
    send_telegram(f"⚡ SEÑAL {direction} - EUR/USD\nPrepara el trade en PO!")
    print(f"✅ Señal: {direction} {pair}")

print("🤖 Bot activo - EUR/USD | EMA cruce + ADX>30")
while True:
    now = datetime.utcnow()
    hour = now.hour
    if 12 <= hour < 21:
        for pair in PAIRS:
            try:
                signal = analyze(pair)
                if signal:
                    write_signal(signal, pair)
            except Exception as e:
                print(f"Error {pair}: {e}")
            time.sleep(60)
    else:
        print(f"Fuera de sesión NY - {now.strftime('%H:%M')} UTC")
        time.sleep(45)
