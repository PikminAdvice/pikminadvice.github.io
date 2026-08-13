import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# 預設掃描池：台股權值股與美股熱門/半導體股 (可自行擴增，建議總數不超過100檔)
TICKERS = {
    "TW": [
        "2330.TW", "2317.TW", "2454.TW", "2382.TW", "2881.TW", 
        "2882.TW", "2891.TW", "3231.TW", "3481.TW", "2308.TW"
    ],
    "US": [
        "AAPL", "MSFT", "NVDA", "TSLA", "MU", "AMZN", "META", 
        "GOOGL", "AMD", "AVGO", "INTC", "QCOM", "ARM", "SMCI"
    ]
}

LOOKBACK_DAYS = 7
STOP_LOSS_PCT = 0.02 # 跌破支撐 2% 即停損

def calculate_indicators(hist):
    recent_hist = hist.tail(LOOKBACK_DAYS)
    support = recent_hist['Low'].min()
    resistance = recent_hist['High'].max()
    stop_loss = support * (1 - STOP_LOSS_PCT)
    
    # 計算 ATR (14日平均真實波動)
    high_low = hist['High'] - hist['Low']
    high_close = np.abs(hist['High'] - hist['Close'].shift())
    low_close = np.abs(hist['Low'] - hist['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    atr = np.max(ranges, axis=1).rolling(14).mean().iloc[-1]
    
    # 爆量偵測
    vol_5d = hist['Volume'].tail(5).mean()
    current_vol = hist['Volume'].iloc[-1]
    is_volume_surge = current_vol > (vol_5d * 1.5)
    
    return support, resistance, stop_loss, atr, is_volume_surge

def evaluate_star_rating(current, support, resistance, stop_loss, is_volume_surge):
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
    radar_data = {"TW": {}, "US": {}}
    
    for market, tickers in TICKERS.items():
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="60d")
                
                if hist.empty or len(hist) < 20: continue
                    
                current_price = hist['Close'].iloc[-1]
                support, resistance, stop_loss, atr, is_volume_surge = calculate_indicators(hist)
                stars, rr_ratio = evaluate_star_rating(current_price, support, resistance, stop_loss, is_volume_surge)
                
                est_days = max(1, int((resistance - current_price) / atr)) if atr > 0 else 7
                
                radar_data[market][ticker] = {
                    "current_price": round(current_price, 2),
                    "support": round(support, 2),
                    "resistance": round(resistance, 2),
                    "stop_loss": round(stop_loss, 2),
                    "stars": stars,
                    "rr_ratio": rr_ratio,
                    "est_days_min": max(1, est_days - 1),
                    "est_days_max": est_days + 2,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                print(f"✅ 掃描完成: {ticker} (現價: {round(current_price,2)})")
            except Exception as e:
                print(f"❌ 掃描失敗 {ticker}: {e}")
                
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(radar_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()