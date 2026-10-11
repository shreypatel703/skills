import csv, sys, json
from analyze1 import cost
ev=list(csv.DictReader(open("codex_events.csv")))+list(csv.DictReader(open("claude_events.csv")))
def span(thread_id,t0,t1):
    tot=out=usd=0.0; n=0
    for e in ev:
        if e["thread_id"]==thread_id and t0<=e["ts"]<=t1:
            inp=int(e["input"]); cached=int(e["cached"]); cw=int(e["cache_write"]); o=int(e["output"])
            if e["tool"]=="codex": fresh=inp-cached; usd+=cost(e["model"],fresh,cached,0,0,o); tot+=inp+o
            else: usd+=cost(e["model"],inp,cached,int(e.get("cache_write_5m") or 0),int(e.get("cache_write_1h") or 0),o); tot+=inp+cached+cw+o
            out+=o; n+=1
    return n,tot,out,usd
if __name__=="__main__":
    for spec in sys.argv[1:]:
        tid,t0,t1=spec.split(",")
        n,tot,out,usd=span(tid,t0,t1); print(f"{tid[:24]} {t0[5:16]}..{t1[5:16]}: {n} requests, {tot/1e6:.1f}M tokens, {out/1e3:.0f}k output, ${usd:.1f}")
