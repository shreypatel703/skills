"""§2.2 by ticket/phase, §2.3 top-20, §2.4 per-thread cache, §2.9 tier fit, §2.10 thinking share."""
import csv, json, collections, re
from analyze1 import PRICE, cost
th=list(csv.DictReader(open("threads.csv")))
for t in th:
    for k in ("wall_seconds","active_seconds","input_tokens","cached_input_tokens","cache_write_tokens","cache_write_1h","cache_write_5m","output_tokens","thinking_tokens","total_tokens","n_tool_calls","test_runs","full_suite_runs","commits_produced","idle_minutes"): t[k]=int(t[k] or 0)
    m=t["model"];
    if t["tool"]=="codex": t["usd"]=cost(m,t["input_tokens"],t["cached_input_tokens"],0,0,t["output_tokens"])
    else: t["usd"]=cost(m,t["input_tokens"],t["cached_input_tokens"],t["cache_write_5m"],t["cache_write_1h"],t["output_tokens"])
def phase(t):
    ap=t["agent_path"]; leaf=ap.split("/")[-1].lower(); r=t["role"]
    if r=="orchestrator": return "orchestrator"
    if r=="merge": return "merge-conflict"
    if r=="implementer":
        if "targeted" in leaf or "rewrite" in leaf: return "targeted-fix"
        return "implement (loop1+loop2, same thread)"
    # reviewer
    if "final" in leaf or "r2" in leaf or "second" in leaf or "rereview" in leaf or "scoped" in leaf or re.search(r"(third|fourth|fifth|v[3-9]|r[3-9]|_r[3-9]|axis_r[2-9])",leaf): return "review-2+ / re-review"
    if "/" in ap[6:] and t["tool"]=="codex" and ap.count("/")>=3: return "review-1 inner pass"
    return "review-1"
for t in th: t["phase"]=phase(t)
# ---- by ticket
byt=collections.defaultdict(collections.Counter)
for t in th:
    c=byt[t["ticket"]]; c["threads"]+=1; c["total"]+=t["total_tokens"]; c["out"]+=t["output_tokens"]; c["think"]+=t["thinking_tokens"]; c["usd"]+=t["usd"]; c["wall"]+=t["wall_seconds"]; c["active"]+=t["active_seconds"]
    c["reviews"]+=1 if t["role"]=="reviewer" else 0; c["tests"]+=t["test_runs"]; c["commits"]+=t["commits_produced"]
print("## by ticket (ranked by tokens)\n| ticket | threads | reviewer threads | total tokens | output | thinking | $ (cache-adj) | thread-wall h | active h | test runs | commits |\n|---|---|---|---|---|---|---|---|---|---|---|")
for k,c in sorted(byt.items(),key=lambda kv:-kv[1]["total"]):
    print(f'| {k} | {c["threads"]} | {c["reviews"]} | {c["total"]/1e6:.1f}M | {c["out"]/1e3:.0f}k | {c["think"]/1e3:.0f}k | {c["usd"]:.0f} | {c["wall"]/3600:.1f} | {c["active"]/3600:.1f} | {c["tests"]} | {c["commits"]} |')
print("\n## by ticket × phase (tokens M / $ / active min)\n")
phases=["implement (loop1+loop2, same thread)","review-1","review-1 inner pass","review-2+ / re-review","targeted-fix","merge-conflict","orchestrator"]
byp=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
for t in th:
    c=byp[t["ticket"]][t["phase"]]; c["total"]+=t["total_tokens"]; c["usd"]+=t["usd"]; c["active"]+=t["active_seconds"]; c["n"]+=1
print("| ticket | "+" | ".join(p.split(" (")[0] for p in phases)+" |"); print("|---|"+"---|"*len(phases))
for k in sorted(byp,key=lambda k:-byt[k]["total"]):
    cells=[]
    for p in phases:
        c=byp[k].get(p)
        cells.append(f'{c["n"]}× {c["total"]/1e6:.1f}M ${c["usd"]:.0f} {c["active"]/60:.0f}m' if c else "-")
    print(f"| {k} | "+" | ".join(cells)+" |")
with open("tables/t2_by_ticket_phase.csv","w") as o:
    w=csv.writer(o); w.writerow(["ticket","phase","threads","total_tokens","usd","active_seconds"])
    for k in byp:
        for p,c in byp[k].items(): w.writerow([k,p,c["n"],c["total"],round(c["usd"],2),c["active"]])
# ---- top 20
def top(key,label):
    print(f"\n## top 20 by {label}\n| # | tool | role | ticket | model/effort | thread | {label} | total tok | output | $ | wall | active | idle gaps | tool calls | tests | commits | outcome |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i,t in enumerate(sorted(th,key=lambda t:-t[key])[:20],1):
        v=f'{t[key]/1e6:.1f}M' if key=="total_tokens" else f'{t[key]/60:.0f} min'
        print(f'| {i} | {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["model"]}/{t["effort"]} | {t["agent_path"][-38:] or t["thread_id"][:8]} | {v} | {t["total_tokens"]/1e6:.1f}M | {t["output_tokens"]/1e3:.0f}k | {t["usd"]:.0f} | {t["wall_seconds"]/60:.0f}m | {t["active_seconds"]/60:.0f}m | {t["idle_gaps_over_5m"]} ({t["idle_minutes"]}m) | {t["n_tool_calls"]} | {t["test_runs"]}/{t["full_suite_runs"]} | {t["commits_produced"]} | {t["outcome"]}{"+resumed" if int(t["resumes"])>0 and t["outcome"]=="killed" else ""} |')
top("total_tokens","tokens"); top("wall_seconds","wall time")
# ---- cache per thread: low hit rate
print("\n## §2.4 threads with lowest cache-hit rate (min 2M tokens) and highest context use\n| tool | role | ticket | thread | total | cache hit % | fresh in | cache write | max ctx % | compactions |\n|---|---|---|---|---|---|---|---|---|---|")
for t in th:
    ctx=t["input_tokens"]+t["cached_input_tokens"]+t["cache_write_tokens"]; t["hit"]=100*t["cached_input_tokens"]/max(1,ctx)
for t in sorted([t for t in th if t["total_tokens"]>2e6],key=lambda t:t["hit"])[:12]:
    print(f'| {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["agent_path"][-36:]} | {t["total_tokens"]/1e6:.1f}M | {t["hit"]:.1f} | {t["input_tokens"]/1e3:.0f}k | {t["cache_write_tokens"]/1e3:.0f}k | {t["max_context_pct"]} | {t["compactions"]} |')
print("\nhighest context-window use:")
for t in sorted(th,key=lambda t:-float(t["max_context_pct"]))[:10]:
    print(f'| {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["agent_path"][-36:]} | max ctx {t["max_context_pct"]}% | compactions {t["compactions"]} | requests {t["api_requests"]} |')
# ---- thinking share by role/model
print("\n## §2.10 thinking/reasoning share\n| tool | model | role | threads | output | thinking | think/output | tool calls | thinking per tool call |\n|---|---|---|---|---|---|---|---|---|")
g=collections.defaultdict(collections.Counter)
for t in th:
    c=g[(t["tool"],t["model"],t["role"])]; c["n"]+=1; c["out"]+=t["output_tokens"]; c["th"]+=t["thinking_tokens"]; c["calls"]+=t["n_tool_calls"]
for k,c in sorted(g.items()):
    if not k[1]: continue
    print(f'| {k[0]} | {k[1]} | {k[2]} | {c["n"]} | {c["out"]/1e3:.0f}k | {c["th"]/1e3:.0f}k | {c["th"]/max(1,c["out"]):.2f} | {c["calls"]} | {c["th"]/max(1,c["calls"]):.0f} |')
print("\nreasoning-heavy, action-light threads (codex; reasoning/output > 0.6 and > 20k reasoning):")
for t in sorted([t for t in th if t["tool"]=="codex" and t["thinking_tokens"]>20000 and t["thinking_tokens"]/max(1,t["output_tokens"])>0.6],key=lambda t:-t["thinking_tokens"]):
    print(f'| {t["role"]} | {t["ticket"]} | {t["agent_path"][-36:]} | reasoning {t["thinking_tokens"]/1e3:.0f}k | output {t["output_tokens"]/1e3:.0f}k | ratio {t["thinking_tokens"]/max(1,t["output_tokens"]):.2f} | tool calls {t["n_tool_calls"]} | files edited {t["files_edited"]} |')
# ---- model tier fit
print("\n## §2.9 model tier used vs policy\n")
SOL_TICKETS={"PZL-97","PZL-98","PZL-99","PZL-100","PZL-101","PZL-102","PZL-119","PZL-120","PZL-107","PZL-108","PZL-109","PZL-110","PZL-121","(orchestrator)"}
print("| tool | role | ticket | thread | model/effort | policy tier | fit | total | $ |\n|---|---|---|---|---|---|---|---|---|")
sav=0
for t in sorted(th,key=lambda t:-t["usd"]):
    if t["total_tokens"]<1e6: continue
    if t["role"]=="reviewer": pol="Sol/opus (policy §4)"
    elif t["role"]=="orchestrator": pol="Sol (policy header)"
    elif t["role"]=="merge": pol="Luna/Terra (mechanical)"
    elif t["ticket"] in SOL_TICKETS: pol="Sol/opus"
    else: pol="Terra/sonnet (default slice)"
    m=t["model"]; used_top = m in ("gpt-5.6-sol","claude-opus-5","claude-fable-5-1")
    if pol.startswith("Luna") and used_top: fit="over-tier"
    elif pol.startswith("Terra") and used_top: fit="over-tier"
    elif pol.startswith("Sol") and not used_top: fit="under-tier"
    else: fit="ok"
    print(f'| {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["agent_path"][-34:]} | {m}/{t["effort"]} | {pol} | {fit} | {t["total_tokens"]/1e6:.1f}M | {t["usd"]:.0f} |')
json.dump(th,open("threads_enriched.json","w"),indent=1)
