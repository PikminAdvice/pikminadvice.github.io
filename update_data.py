import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# 設定台美股觀察清單
TICKERS = {
    "TW": ["2330.TW", "2317.TW", "2454.TW", "2382.TW"],
    "US": ["AAPL", "MSFT", "NVDA", "TSLA", "MU"]
}

# 策略參數
LOOKBACK_DAYS = 7
STOP_LOSS_PCT = 0.02 # 跌破支撐 2% 停損

def calculate_indicators(hist):
    """計算支撐、壓力、ATR與爆量"""
    recent_hist = hist.tail(LOOKBACK_DAYS)
    support = recent_hist['Low'].min()
    resistance = recent_hist['High'].max()
    stop_loss = support * (1 - STOP_LOSS_PCT)
    
    # 計算 ATR (Average True Range) - 抓 14 天均值
    high_low = hist['High'] - hist['Low']
    high_close = np.abs(hist['High'] - hist['Close'].shift())
    low_close = np.abs(hist['Low'] - hist['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(14).mean().iloc[-1]
    
    # 爆量偵測：當日量大於近 5 日均量 1.5 倍
    vol_5d = hist['Volume'].tail(5).mean()
    current_vol = hist['Volume'].iloc[-1]
    is_volume_surge = current_vol > (vol_5d * 1.5)
    
    return support, resistance, stop_loss, atr, is_volume_surge

def evaluate_star_rating(current, support, resistance, stop_loss, is_volume_surge):
    """計算盈虧比並給予 1~5 星評等"""
    # 避免除以零
    if current <= stop_loss:
        return 1, 0
        
    reward = resistance - current
    risk = current - stop_loss
    rr_ratio = reward / risk if risk > 0 else 0
    
    # 星級評分邏輯
    stars = 1
    if rr_ratio > 2.5 and is_volume_surge:
        stars = 5
    elif rr_ratio > 2.0:
        stars = 4
    elif rr_ratio > 1.5:
        stars = 3
    elif rr_ratio > 1.0:
        stars = 2
        
    return stars, round(rr_ratio, 2)

def main():
    radar_data = {"TW": {}, "US": {}}
    
    for market, tickers in TICKERS.items():
        for ticker in tickers:
            try:
                # 抓取近 60 天資料以利計算均線與 ATR
                stock = yf.Ticker(ticker)
                hist = stock.history(period="60d")
                
                if hist.empty or len(hist) < 20:
                    continue
                    
                current_price = hist['Close'].iloc[-1]
                support, resistance, stop_loss, atr, is_volume_surge = calculate_indicators(hist)
                stars, rr_ratio = evaluate_star_rating(current_price, support, resistance, stop_loss, is_volume_surge)
                
                # 預估天數：距離目標價的空間 / 每日平均波動(ATR)
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
                    "is_volume_surge": is_volume_surge,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                print(f"Processed {ticker} - Stars: {stars}")
                
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(radar_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()