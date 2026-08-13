import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime
import time

# --- 1. 定義掃描範圍 ---
def get_us_tickers():
    try:
        # 自動爬取維基百科最新 S&P 500 名單
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)[0]
        tickers = table['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers] # yfinance 格式修正
    except:
        # 備用清單 (若維基百科連線失敗)
        return ["AAPL", "MSFT", "NVDA", "TSLA", "MU", "AMZN", "META", "GOOGL", "AMD"]

def get_tw_tickers():
    # 台灣 50 + 中型 100 核心權值股 (此處列出前 50 檔作為示範，你可隨時擴增)
    return [
        "2330.TW", "2317.TW", "2454.TW", "2382.TW", "2881.TW", "2882.TW", "2891.TW",
        "3231.TW", "3481.TW", "2308.TW", "2303.TW", "2886.TW", "2884.TW", "2885.TW",
        "1216.TW", "1301.TW", "1303.TW", "2002.TW", "2603.TW", "2609.TW", "3711.TW"
    ]

LOOKBACK_DAYS = 7
STOP_LOSS_PCT = 0.02

def calculate_indicators(hist):
    recent_hist = hist.tail(LOOKBACK_DAYS)
    support = recent_hist['Low'].min()
    resistance = recent_hist['High'].max()
    stop_loss = support * (1 - STOP_LOSS_PCT)
    
    high_low = hist['High'] - hist['Low']
    high_close = np.abs(hist['High'] - hist['Close'].shift())
    low_close = np.abs(hist['Low'] - hist['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    atr = np.max(ranges, axis=1).rolling(14).mean().iloc[-1]
    
    vol_5d = hist['Volume'].tail(5).mean()
    current_vol = hist['Volume'].iloc[-1]
    is_volume_surge = current_vol > (vol_5d * 1.5)
    
    return support, resistance, stop_loss, atr, is_volume_surge

def evaluate_stars(current, support, resistance, stop_loss, is_volume_surge):
    if current <= stop_loss: return 1, 0
    reward = resistance - current
    risk = current - stop_loss
    rr_ratio = reward / risk if risk > 0 else 0
    
    stars = 1
    if rr_ratio > 2.5 and is_volume_surge: stars = 5
    elif rr_ratio > 2.0: stars = 4
    elif rr_ratio > 1.5: stars = 3
    elif rr_ratio > 1.0: stars = 2
    return stars, round(rr_ratio, 2)

def main():
    print("開始執行深夜全市場掃描...")
    market_tickers = {"TW": get_tw_tickers(), "US": get_us_tickers()}
    candidates = {"TW": {}, "US": {}}
    
    for market, tickers in market_tickers.items():
        # 為了避免被封鎖，我們分批下載，並在批次間休息
        batch_size = 50
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            data = yf.download(batch, period="60d", group_by="ticker", progress=False)
            
            for ticker in batch:
                try:
                    # 處理單一股票或多股票返回的資料結構差異
                    hist = data[ticker] if len(batch) > 1 else data
                    hist = hist.dropna()
                    if len(hist) < 20: continue
                    
                    current_price = hist['Close'].iloc[-1]
                    support, resistance, stop_loss, atr, is_vol_surge = calculate_indicators(hist)
                    stars, rr_ratio = evaluate_stars(current_price, support, resistance, stop_loss, is_vol_surge)
                    
                    # 只紀錄大於等於 3 星的候選股
                    if stars >= 3:
                        est_days = max(1, int((resistance - current_price) / atr)) if atr > 0 else 7
                        candidates[market][ticker] = {
                            "current_price": round(current_price, 2),
                            "support": round(support, 2),
                            "resistance": round(resistance, 2),
                            "stop_loss": round(stop_loss, 2),
                            "stars": stars,
                            "rr_ratio": rr_ratio,
                            "est_days_min": max(1, est_days - 1),
                            "est_days_max": est_days + 2,
                            "atr": round(atr, 2) # 留給盤中腳本計算用
                        }
                except Exception as e:
                    pass
            time.sleep(2) # 休息2秒防封鎖
            
        # 針對該市場進行排序，只保留前 30 名
        sorted_candidates = dict(sorted(candidates[market].items(), key=lambda x: x[1]['rr_ratio'], reverse=True)[:30])
        candidates[market] = sorted_candidates
        print(f"✅ {market} 市場掃描完畢，選出 {len(sorted_candidates)} 檔候選股。")

    with open("candidates.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()