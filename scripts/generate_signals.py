#!/usr/bin/env python3
"""Daily PSX end-of-day signal generator. Uses delayed daily OHLCV from PSX Lens.
Never emits a signal for a symbol without sufficient, current, validated history.
"""
import json, os, sys, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = "https://api.psxlens.com"
UA = "PSX-AI-INTELLIGENCE/1.0 (daily research scanner)"
def get(path):
    req = Request(BASE + path, headers={"User-Agent": UA, "Accept":"application/json"})
    with urlopen(req, timeout=35) as r:
        if r.status != 200: raise RuntimeError(f"API {r.status}: {path}")
        return json.loads(r.read().decode("utf-8"))

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values(): yield from walk(v)
    elif isinstance(obj, list):
        for v in obj: yield from walk(v)

def symbol_rows(payload):
    out = {}
    for x in walk(payload):
        s = x.get("symbol") or x.get("ticker")
        if isinstance(s,str) and 2 <= len(s) <= 15:
            out[s.upper()] = x
    return out

def bars_from(payload, symbol):
    found=[]
    for x in walk(payload):
        # Candidate daily bar shape
        date = x.get("date") or x.get("session_date") or x.get("trading_date")
        close = x.get("close") or x.get("close_price") or x.get("closing")
        if date and close is not None:
            try:
                c=float(close)
                if c>0:
                    found.append({"date":str(date)[:10],"open":float(x.get("open") or c),
                                  "high":float(x.get("high") or c),"low":float(x.get("low") or c),
                                  "close":c,"volume":float(x.get("volume") or x.get("vol") or 0)})
            except (TypeError,ValueError): pass
    # deduplicate dates and sort
    dedup={b["date"]:b for b in found}
    return sorted(dedup.values(),key=lambda b:b["date"])[-260:]

def ema(values, period):
    if len(values)<period: return None
    k=2/(period+1); v=sum(values[:period])/period
    for x in values[period:]: v=x*k+v*(1-k)
    return v

def rsi(values, period=14):
    if len(values)<period+1:return None
    changes=[values[i]-values[i-1] for i in range(1,len(values))]
    gains=[max(x,0) for x in changes]; losses=[max(-x,0) for x in changes]
    ag=sum(gains[:period])/period; al=sum(losses[:period])/period
    for i in range(period,len(changes)):
        ag=(ag*(period-1)+gains[i])/period; al=(al*(period-1)+losses[i])/period
    return 100 if al==0 else 100-100/(1+ag/al)

def macd(values):
    if len(values)<35:return None,None
    fast=[]; slow=[]
    for i in range(len(values)):
        fast.append(ema(values[:i+1],12)); slow.append(ema(values[:i+1],26))
    line=[a-b for a,b in zip(fast,slow) if a is not None and b is not None]
    if len(line)<9:return None,None
    sig=ema(line,9)
    return line[-1],sig

def atr(bars, period=14):
    if len(bars)<period+1:return None
    tr=[]
    for i in range(1,len(bars)):
        b,p=bars[i],bars[i-1]
        tr.append(max(b["high"]-b["low"],abs(b["high"]-p["close"]),abs(b["low"]-p["close"])))
    return sum(tr[-period:])/period

def adx(bars, period=14):
    if len(bars)<period*2+1:return None
    plus=[]; minus=[]; trs=[]
    for i in range(1,len(bars)):
        cur,prev=bars[i],bars[i-1]
        up=cur["high"]-prev["high"]; dn=prev["low"]-cur["low"]
        plus.append(up if up>dn and up>0 else 0)
        minus.append(dn if dn>up and dn>0 else 0)
        trs.append(max(cur["high"]-cur["low"],abs(cur["high"]-prev["close"]),abs(cur["low"]-prev["close"])))
    dx=[]
    for i in range(period-1,len(trs)):
        tr=sum(trs[i-period+1:i+1])
        if tr<=0:continue
        p=100*sum(plus[i-period+1:i+1])/tr; m=100*sum(minus[i-period+1:i+1])/tr
        dx.append(100*abs(p-m)/(p+m) if p+m else 0)
    return sum(dx[-period:])/len(dx[-period:]) if len(dx)>=period else None

def analyse(symbol,bars):
    if len(bars)<205:return None
    closes=[b["close"] for b in bars]; vols=[b["volume"] for b in bars]
    c=closes[-1]; e20,e50,e100,e200=[ema(closes,p) for p in (20,50,100,200)]
    rv=sum(vols[-20:])/20; rel=vols[-1]/rv if rv else 0
    r=rsi(closes); rprev=rsi(closes[:-1]); m,ms=macd(closes); a=adx(bars); av=atr(bars)
    weekly=closes[::] # Aggregate the last completed five-session closes
    wclose=[closes[i] for i in range(4,len(closes),5)]
    we20=ema(wclose,20); we50=ema(wclose,50)
    trend=30 if c>e20>e50>e100>e200 else (15 if c>e20>e50 else 0)
    momentum=20 if r is not None and 55<=r<=70 and rprev is not None and r>rprev and m is not None and ms is not None and m>ms else (10 if m is not None and ms is not None and m>ms else 0)
    volume=15 if rel>=1.5 and len(vols)>=3 and vols[-1]>vols[-2] and vols[-2]<=vols[-3] else 0
    prior_high=max(b["high"] for b in bars[-21:-1])
    breakout= c>prior_high
    price=20 if breakout else (10 if c>e20 and c>=max(closes[-5:]) else 0)
    weekly_pts=15 if we20 is not None and we50 is not None and wclose[-1]>we20>we50 else 0
    score=trend+momentum+volume+price+weekly_pts
    status="STRONG BUY" if score>=80 else "BUY" if score>=70 else "WAIT" if score>=60 else "SELL" if c<e50 and r is not None and r<45 else "HOLD"
    stop=round(c-1.5*av,2) if av else None
    risk=(c-stop) if stop else None
    return {"symbol":symbol,"date":bars[-1]["date"],"close":round(c,2),"change_pct":round((c/closes[-2]-1)*100,2) if closes[-2] else None,
      "score":score,"signal":status,"entry":round(c,2),"stop_loss":stop,
      "tp1":round(c+risk,2) if risk else None,"tp2":round(c+2*risk,2) if risk else None,"tp3":round(c+3*risk,2) if risk else None,
      "rsi14":round(r,1) if r is not None else None,"adx14":round(a,1) if a is not None else None,
      "relative_volume":round(rel,2),"ema20":round(e20,2),"ema50":round(e50,2),"ema100":round(e100,2),"ema200":round(e200,2),
      "macd_bullish":bool(m is not None and ms is not None and m>ms),"weekly_bullish":bool(weekly_pts),
      "breakout":bool(breakout),"volume_cross":bool(volume),"atr14":round(av,2) if av else None,
      "score_components":{"trend":trend,"momentum":momentum,"volume":volume,"price_action":price,"weekly":weekly_pts}}

def main():
    os.makedirs("data",exist_ok=True)
    # Full market close sheet supplies the current session and active universe.
    summary=get("/v1/market/summary")
    syms=sorted(symbol_rows(summary).keys())
    if not syms: raise RuntimeError("Could not identify listed symbols in market summary; refusing to publish empty/false signals.")
    results=[]
    for start in range(0,len(syms),25):
        batch=syms[start:start+25]
        payload=get("/v1/prices?symbols="+",".join(batch)+"&limit=260")
        for s in batch:
            bars=bars_from(payload,s)
            if len(bars)>=205:
                row=analyse(s,bars)
                if row: results.append(row)
        time.sleep(.25)
    if not results: raise RuntimeError("No symbols had enough valid daily history; keep the previous signal file.")
    results.sort(key=lambda x:(x["score"],x["relative_volume"]),reverse=True)
    latest=max(x["date"] for x in results)
    output={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"session_date":latest,
      "data_source":"PSX Lens API (delayed end-of-day data)","attribution":"Data by PSX Lens (psxlens.com)",
      "mode":"automated_daily_eod","universe_scanned":len(syms),"symbols_with_valid_history":len(results),
      "signals":results,"method":"PSX AI INTELLIGENCE 20/80 adaptation; daily OHLCV; weekly close approximation from 5-session closes.",
      "disclaimer":"Research only, not investment advice. Signals are rule-based and may be wrong. Verify prices, corporate actions, liquidity and announcements before trading."}
    with open("data/signals.json","w",encoding="utf-8") as f: json.dump(output,f,ensure_ascii=False,indent=2)
    print(f"Published {len(results)} calculated symbols for {latest} from universe {len(syms)}")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("Signal generation failed:",e,file=sys.stderr); sys.exit(1)
