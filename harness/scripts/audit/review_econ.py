import csv, json, re, collections
th={t["thread_id"]:t for t in json.load(open("threads_enriched.json"))}
fi={r["thread_id"]:r for r in csv.DictReader(open("finals_index.csv"))}
def sev(txt):
    # count finding bullets by severity marker in the LAST message
    p1=len(re.findall(r"\*\*\s*\[?(P1|BLOCKER|Blocker|High(?: ·|\s*\u2014|\s*-|,| ))",txt))+len(re.findall(r"\[(P1|Blocker|High[^\]]*)\]",txt))
    p2=len(re.findall(r"\*\*\s*\[?(P2|MAJOR|Medium)",txt))+len(re.findall(r"\[(P2|Medium)\]",txt))
    p3=len(re.findall(r"\*\*\s*\[?(P3|MINOR|Low)",txt))+len(re.findall(r"\[(P3|Low)\]",txt))
    clean=bool(re.search(r"\b(no (actionable |remaining |documented-standard |spec )?findings|0 findings|No findings|zero findings|CLEAN|PASS\b|no blockers|0 blockers|clean)\b",txt))
    return p1,p2,p3,clean
rows=[]
for tid,t in th.items():
    if t["role"]!="reviewer": continue
    txt=open(f"finals/{tid}.md").read()
    last=txt.split("\n\n---\n\n")[-1] if txt else ""
    p1,p2,p3,clean=sev(last)
    rows.append(dict(ticket=t["ticket"],thread=t["agent_path"][-40:],tool=t["tool"],start=t["start_ts"][5:16],tokens=int(t["total_tokens"]),usd=round(t["usd"],1),active_min=int(t["active_seconds"])//60,msgs=fi[tid]["n_msgs"],p1=p1,p2=p2,p3=p3,clean=int(clean and p1==0),tests=int(t["test_runs"])))
rows.sort(key=lambda r:(r["ticket"],r["start"]))
with open("tables/t6_reviews.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("| ticket | review thread | tool | start | tokens | $ | active min | msgs | P1/blocker-class | P2/major | P3/minor | clean verdict | tests run |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows: print(f'| {r["ticket"]} | {r["thread"]} | {r["tool"]} | {r["start"]} | {r["tokens"]/1e6:.1f}M | {r["usd"]} | {r["active_min"]} | {r["msgs"]} | {r["p1"]} | {r["p2"]} | {r["p3"]} | {"✓" if r["clean"] else ""} | {r["tests"]} |')
# per ticket summary
print("\n| ticket | review threads | review tokens | review $ | P1-class findings (sum over passes) | tokens per P1-class finding |\n|---|---|---|---|---|---|")
g=collections.defaultdict(collections.Counter)
for r in rows:
    c=g[r["ticket"]]; c["n"]+=1; c["tok"]+=r["tokens"]; c["usd"]+=r["usd"]; c["p1"]+=r["p1"]
for k,c in sorted(g.items(),key=lambda kv:-kv[1]["tok"]): print(f'| {k} | {c["n"]} | {c["tok"]/1e6:.1f}M | {c["usd"]:.0f} | {c["p1"]} | {c["tok"]/1e6/max(1,c["p1"]):.1f}M |')
