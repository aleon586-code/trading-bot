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
    symbol = pair
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=50&apikey={TD_API_KEY}"
    r = requests.get(url)
    df = pd.DataFrame(r.json()["values"])
    df = df.astype({"open":float,"high":float,"low":float,"close":float})
    return df.iloc[::-1].reset_index(drop=True)

def analyze(pair):
    df = get_candles(pair)
    ema8 = df["close"].ewm(span=8).mean()
    ema21 = df["close"].ewm(span=21).mean()
    low_min = df["low"].rolling(5).min()
    high_max = df["high"].rolling(5).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(3).mean()
    last = df.index[-1]
    prev = last - 1
    trend_up = ema8.iloc[last] > ema21.iloc[last]
    trend_dn = ema8.iloc[last] < ema21.iloc[last]
    cross_up = k.iloc[prev] < d.iloc[prev] and k.iloc[last] > d.iloc[last]
    cross_dn = k.iloc[prev] > d.iloc[prev] and k.iloc[last] < d.iloc[last]
    green = df["close"].iloc[last] > df["open"].iloc[last]
    red = df["close"].iloc[last] < df["open"].iloc[last]
    if trend_up and k.iloc[last] < 35 and cross_up and green:
        return "CALL"
    if trend_dn and k.iloc[last] > 65 and cross_dn and red:
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

print("🤖 Bot activo - EUR/USD")
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
            time.sleep(10)
    else:
        print(f"Fuera de sesión NY - {now.strftime('%H:%M')} UTC")
        time.sleep(45)
