"""§2.1 totals by model/tool/day + cost; §2.3 top threads; §2.4 cache; §2.10 thinking share."""
import csv, json, collections, datetime as dt
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
def pt(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
# ---- price table (ASSUMPTION; $ per 1M tokens) ----
from prices import PRICE, cost_usd as cost
ev=list(csv.DictReader(open("codex_events.csv")))+list(csv.DictReader(open("claude_events.csv")))
ev=[e for e in ev if e["in_window"]=="1"]
agg=collections.defaultdict(lambda:collections.Counter())
for e in ev:
    tool=e["tool"]; m=e["model"] or "?"
    day=pt(e["ts"]).astimezone(NY).strftime("%m-%d")
    inp=int(e["input"]); cached=int(e["cached"]); cw=int(e["cache_write"]); out=int(e["output"])
    think=int(e.get("thinking") or e.get("reasoning") or 0)
    if tool=="codex": fresh=inp-cached; w5=0; w1=0  # codex cache_write reported separately (0 in all files)
    else: fresh=inp; w5=int(e.get("cache_write_5m") or 0); w1=int(e.get("cache_write_1h") or 0)
    for key in ((tool,m,day),(tool,m,"all"),(tool,"all","all"),("all","all","all")):
        c=agg[key]; c["requests"]+=1; c["fresh"]+=fresh; c["cached"]+=cached; c["cache_write"]+=cw; c["w5"]+=w5; c["w1"]+=w1; c["output"]+=out; c["thinking"]+=think
        c["total"]+=fresh+cached+cw+out
        c["cost_adj"]+=cost(m,fresh,cached,w5,w1,out); c["cost_list"]+=cost(m,fresh,cached,w5,w1,out,True)
rows=[]
import sys as _s
_Q=(__name__!="__main__")
for (tool,m,day),c in sorted(agg.items()):
    rows.append(dict(tool=tool,model=m,day=day,requests=c["requests"],fresh_input=c["fresh"],cache_read=c["cached"],cache_write=c["cache_write"],cw_5m=c["w5"],cw_1h=c["w1"],output=c["output"],thinking=c["thinking"],total=c["total"],
                     cache_hit_pct=round(100*c["cached"]/max(1,c["fresh"]+c["cached"]+c["cache_write"]),1),cost_list_usd=round(c["cost_list"],2),cost_cache_adj_usd=round(c["cost_adj"],2)))
with open("tables/t1_totals_by_model.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
def M(x): return f"{x/1e6:.1f}M"
if not _Q: print("| tool | model | day | requests | fresh in | cache read | cache write (5m/1h) | output | thinking | total | cache hit % | $ list | $ cache-adj |")
if not _Q: print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    if r["model"]=="?" or _Q: continue
    print(f'| {r["tool"]} | {r["model"]} | {r["day"]} | {r["requests"]} | {M(r["fresh_input"])} | {M(r["cache_read"])} | {M(r["cache_write"])} ({M(r["cw_5m"])}/{M(r["cw_1h"])}) | {r["output"]/1e3:.0f}k | {r["thinking"]/1e3:.0f}k | {M(r["total"])} | {r["cache_hit_pct"]} | {r["cost_list_usd"]:.0f} | {r["cost_cache_adj_usd"]:.0f} |')
# wall time per model: sum of per-thread active seconds attributed to model of thread
th=list(csv.DictReader(open("threads.csv")))
wt=collections.Counter(); at=collections.Counter()
for t in th:
    wt[(t["tool"],t["model"])]+=int(t["wall_seconds"]); at[(t["tool"],t["model"])]+=int(t["active_seconds"])
if not _Q: print("\nwall/active hours by (tool, model) [thread-level, overlapping threads summed]:")
for k in sorted(wt): _Q or print(f"| {k[0]} | {k[1]} | wall {wt[k]/3600:.1f} h | active {at[k]/3600:.1f} h |")
