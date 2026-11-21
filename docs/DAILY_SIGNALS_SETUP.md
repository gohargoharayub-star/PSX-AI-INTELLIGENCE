# Daily signal engine
GitHub Actions runs at 16:45 Pakistan time on weekdays; run manually from Actions to test.
Add repository Actions secrets:
- PSX_DATA_CSV_URL: HTTPS URL returning OHLCV CSV
- PSX_DATA_TOKEN: optional bearer token
- PSX_DATA_LICENSE_CONFIRMED: true only when your provider permits processing and public display
CSV columns: symbol,date,open,high,low,close,volume. Supply at least 220 daily sessions per ticker. Use adjusted data where available.
Scoring: trend 30 (EMA20>50>100 and EMA100>200); momentum 20 (RSI14 55–70 rising and MACD bullish); volume 15 (relative volume >=1.5 plus volume-cross); price action 20 (20-session breakout / EMA20 extension <=6%); weekly 15 (weekly close above EMA20 and EMA50). Filters ADX14>=20 and extension<=6%. Entry=close; stop=1.5 ATR below; targets=2R,3R,4R. Strong Buy >=80 only when all mandatory checks pass. Sell requires bearish close below EMA20/50, bearish MACD and RSI<45. This is a screening aid, not financial advice or trade execution.
Data licensing: https://www.psx.com.pk/psx/product-and-services/data-services-vending
