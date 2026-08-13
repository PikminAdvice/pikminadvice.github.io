import yfinance as yf
import json
from datetime import datetime

# 💡 這裡請填入你在網頁上持有的股票，確保它們的價格每半小時都會更新！
USER_HOLDINGS = ["MU", "AAPL", "2330.TW", "2317.TW"] 

def main():
    print("開始盤中更新報價...")
    
    # 讀取深夜掃描的候選名單
    try:
        with open("candidates.json", "r", encoding="utf-8") as f:
            candidates = json.load(f)
    except FileNotFoundError:
        print("尚未發現 candidates.json，請先執行 daily_scan.py")
        candidates = {"TW": {}, "US": {}}
        
    radar_data = {"TW": {}, "US": {}}
    
    for market in ["TW", "US"]:
        # 組合「候選名單」與「使用者持股」
        target_tickers = list(candidates[market].keys())
        
        # 把使用者的持股分發到對應的市場中
        for holding in USER_HOLDINGS:
            if (market == "TW" and ".TW" in holding) or (market == "US" and ".TW" not in holding):
                if holding not in target_tickers:
                    target_tickers.append(holding)
        
        if not target_tickers: continue
        
        # 盤中只需要抓 1 天的最新資料
        data = yf.download(target_tickers, period="1d", group_by="ticker", progress=False)
        
        for ticker in target_tickers:
            try:
                hist = data[ticker] if len(target_tickers) > 1 else data
                if hist.empty: continue
                
                current_price = round(hist['Close'].iloc[-1], 2)
                
                # 如果這檔股票是昨晚掃描出的候選股，更新價格並重新計算盈虧比
                if ticker in candidates[market]:
                    info = candidates[market][ticker]
                    info['current_price'] = current_price
                    
                    # 重新計算星級與盈虧比 (因為盤中價格變動了)
                    reward = info['resistance'] - current_price
                    risk = current_price - info['stop_loss']
                    info['rr_ratio'] = round(reward / risk, 2) if risk > 0 else 0
                    
                    if current_price <= info['stop_loss']: info['stars'] = 1
                    elif info['rr_ratio'] > 2.5: info['stars'] = 5
                    elif info['rr_ratio'] > 2.0: info['stars'] = 4
                    elif info['rr_ratio'] > 1.5: info['stars'] = 3
                    else: info['stars'] = 2
                    
                    radar_data[market][ticker] = info
                else:
                    # 如果這檔純粹是使用者的持股 (不在推薦名單內)，只更新現價給前端資產計算用
                    radar_data[market][ticker] = {
                        "current_price": current_price,
                        "stars": 0 # 0 星代表前端不會將其顯示在雷達推薦中
                    }
                    
            except Exception as e:
                pass

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(radar_data, f, ensure_ascii=False, indent=2)
    print("✅ 盤中報價更新完成 (data.json)")

if __name__ == "__main__":
    main()