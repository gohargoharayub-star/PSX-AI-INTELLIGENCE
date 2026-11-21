#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data/signals.json"
INPUT=Path(os.getenv("PSX_OHLCV_CSV",ROOT/"data/ohlcv.csv"))
REQ={"symbol","date","open","high","low","close","volume"}
def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
 d=s.diff(); up=d.clip(lower=0); dn=-d.clip(upper=0)
 a=up.ewm(alpha=1/n,min_periods=n,adjust=False).mean(); b=dn.ewm(alpha=1/n,min_periods=n,adjust=False).mean()
 return 100-100/(1+a/b.replace(0,np.nan))
def atr(x,n=14):
 pc=x.close.shift(); tr=pd.concat([x.high-x.low,(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1)
 return tr.ewm(alpha=1/n,min_periods=n,adjust=False).mean()
def adx(x,n=14):
 u=x.high.diff(); d=-x.low.diff(); p=pd.Series(np.where((u>d)&(u>0),u,0),index=x.index); m=pd.Series(np.where((d>u)&(d>0),d,0),index=x.index)
 a=atr(x,n).replace(0,np.nan); pdi=100*p.ewm(alpha=1/n,adjust=False).mean()/a; mdi=100*m.ewm(alpha=1/n,adjust=False).mean()/a
 dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
 return dx.ewm(alpha=1/n,adjust=False).mean()
def num(v):
 return None if pd.isna(v) or not np.isfinite(v) else round(float(v),2)
def scan(sym,g):
 x=g.sort_values("date").drop_duplicates("date").copy()
 for k in ["open","high","low","close","volume"]: x[k]=pd.to_numeric(x[k],errors="coerce")
 x=x.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)
 if len(x)<220 or (x.close<=0).any(): return None
 c=x.close; v=x.volume
 for n in [20,50,100,200]: x["e"+str(n)]=ema(c,n)
 x["rsi"]=rsi(c); x["atr"]=atr(x); x["adx"]=adx(x)
 mac=ema(c,12)-ema(c,26); sig=ema(mac,9); hist=mac-sig
 x["mac"],x["sig"],x["hist"]=mac,sig,hist
 x["rv"]=v/v.rolling(20).mean().replace(0,np.nan)
 x["bo"]=c>x.high.shift().rolling(20).max()
 w=x.set_index("date").resample("W-FRI").agg({"close":"last"}).dropna()
 if len(w)<55:return None
 w20=ema(w.close,20);w50=ema(w.close,50);wk=bool(w.close.iloc[-1]>w20.iloc[-1]>w50.iloc[-1])
 a=x.iloc[-1];b=x.iloc[-2];z=x.iloc[-3]
 trend=bool(a.close>a.e20>a.e50>a.e100 and a.e100>a.e200)
 mom=bool(55<=a.rsi<=70 and a.rsi>b.rsi and a.mac>a.sig and a.hist>0 and a.hist>b.hist)
 vc=bool(a.volume>b.volume and b.volume<=z.volume); vol=bool(a.rv>=1.5 and vc)
 ext=(a.close/a.e20-1)*100 if a.e20 else 999
 ad=bool(a.adx>=20); br=bool(a.bo)
 score=(30 if trend else (15 if a.close>a.e50 else 0))+(20 if mom else (8 if a.rsi>=50 and a.mac>a.sig else 0))+(15 if vol else (5 if a.rv>=1 else 0))+(20 if br and ext<=6 else (10 if a.close>a.e20 and ext<=6 else 0))+(15 if wk else 0)
 filt=ad and ext<=6
 if trend and mom and vol and wk and filt and score>=80:s="STRONG BUY"
 elif trend and wk and filt and score>=70:s="BUY"
 elif a.close<a.e20 and a.close<a.e50 and a.mac<a.sig and a.rsi<45:s="SELL"
 elif score>=60:s="WAIT"
 else:s="NO TRADE"
 entry=float(a.close); risk=1.5*float(a.atr)
 return {"symbol":sym,"date":str(pd.to_datetime(a.date).date()),"close":num(entry),"rsi14":num(a.rsi),"relative_volume":num(a.rv),"adx14":num(a.adx),"score":int(round(score)),"signal":s,"entry":num(entry),"stop_loss":num(entry-risk),"tp1":num(entry+2*risk),"tp2":num(entry+3*risk),"tp3":num(entry+4*risk),"weekly_confirmed":wk,"breakout_20d":br,"trend_confirmed":trend,"momentum_confirmed":mom,"volume_cross":vc,"filters_passed":filt}
def main():
 if not INPUT.exists(): payload={"status":"data_not_configured","message":"Authorized OHLCV CSV source not configured.","session_date":None,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"symbols_with_valid_history":0,"signals":[]}
 else:
  d=pd.read_csv(INPUT); miss=REQ-set(d.columns)
  if miss: raise ValueError("Missing CSV columns: "+", ".join(sorted(miss)))
  d["date"]=pd.to_datetime(d.date,errors="coerce");d=d.dropna(subset=["date"]);out=[]
  for s,g in d.groupby(d.symbol.astype(str).str.upper()):
   try:
    r=scan(s,g)
    if r:out.append(r)
   except Exception as e:print("Skip",s,e,file=sys.stderr)
  out.sort(key=lambda q:q["score"],reverse=True)
  payload={"status":"ok" if out else "no_valid_history","message":"Calculated from supplied OHLCV dataset; verify before trading.","session_date":max([q["date"] for q in out],default=None),"generated_at_utc":datetime.now(timezone.utc).isoformat(),"symbols_with_valid_history":len(out),"signals":out}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2))
 print("Signals:",len(payload["signals"]),payload["status"])
if __name__=="__main__":main()
