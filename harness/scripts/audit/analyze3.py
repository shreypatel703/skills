"""§2.5 repeated/redundant work, §2.7 orchestrator overhead, §2.8 idle."""
import csv, json, re, collections, datetime as dt
def pt(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
th={t["thread_id"]:t for t in json.load(open("threads_enriched.json"))}
acts=list(csv.DictReader(open("actions.csv")))
by=collections.defaultdict(list)
for a in acts: by[a["thread_id"]].append(a)
def isbash(a): return (a["tool"]=="codex" and a["kind"]=="exec") or (a["tool"]=="claude" and a["name"]=="Bash")
TEST=re.compile(r"\b(pytest|vitest|pnpm (run )?test|make (fe-)?test)\b")
def is_full(cmd):
    # a pytest/vitest invocation with no path argument (allowing flags), or make test / make fe-test / pnpm test with no filter
    if re.search(r"\bmake (fe-)?test\b",cmd): return True
    for m in re.finditer(r"(?:uv run |python -m )?pytest\b([^;&|\n]*)",cmd):
        args=m.group(1)
        toks=[x for x in args.split() if not x.startswith("-") and not x.startswith("$")]
        # drop values of -k/-p/-o/--maxfail style options
        args2=re.sub(r"-(k|p|o|m|W|n|x)\s+\S+","",args); args2=re.sub(r"--\S+(=\S+)?","",args2); args2=re.sub(r"-\S+","",args2)
        if not [x for x in args2.split() if x and not x.startswith("$")]: return True
    if re.search(r"pnpm (run )?test\s*($|[;&|>])|pnpm vitest run\s*($|[;&|>])|npx vitest run\s*($|[;&|>])",cmd): return True
    return False
print("## §2.5 test-suite invocations per thread (threads with >=5)\n| tool | role | ticket | thread | test runs | full-suite runs | test wall min | longest run (s) |\n|---|---|---|---|---|---|---|---|")
tot_full=[]; rows=[]
for tid,t in th.items():
    A=[a for a in by.get(tid,[]) if isbash(a) and TEST.search(a["cmd"])]
    full=[a for a in A if is_full(a["cmd"])]
    for a in full: tot_full.append((a["ts"],t["tool"],t["role"],t["ticket"],t["agent_path"][-30:],float(a["dur_s"] or 0),a["cmd"][:140]))
    secs=sum(float(a["dur_s"] or 0) for a in A); mx=max([float(a["dur_s"] or 0) for a in A],default=0)
    if len(A)>=5: rows.append((len(A),f'| {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["agent_path"][-32:]} | {len(A)} | {len(full)} | {secs/60:.0f} | {mx:.0f} |'))
for n,r in sorted(rows,reverse=True): print(r)
print(f"\nfull-suite runs (no path): {len(tot_full)}, total {sum(x[5] for x in tot_full)/60:.0f} min\n| ts | tool | role | ticket | thread | dur s | cmd |\n|---|---|---|---|---|---|---|")
for x in sorted(tot_full): print(f"| {x[0][5:16]} | {x[1]} | {x[2]} | {x[3]} | {x[4]} | {x[5]:.0f} | `{x[6].replace('|','\\|')}` |")
json.dump(tot_full,open("tables/t5_full_suite_runs.json","w"),indent=1)
# repeated file reads
print("\n## same file read >3 times in one thread (top)\n| tool | role | ticket | thread | file | reads |\n|---|---|---|---|---|---|")
rr=[]
for tid,t in th.items():
    c=collections.Counter()
    for a in by.get(tid,[]):
        if a["tool"]=="claude" and a["name"]=="Read": c[a["cmd"]]+=1
        elif isbash(a):
            for m in re.finditer(r"(?:sed -n '[^']*' |cat |head [^|]*?|bat )([\w./-]+\.(?:py|md|ts|tsx|json|toml|yml|yaml|sh|css))",a["cmd"]): c[m.group(1)]+=1
    for f,n in c.items():
        if n>3: rr.append((n,t["tool"],t["role"],t["ticket"],t["agent_path"][-30:],f))
for n,tool,role,tk,ap,f in sorted(rr,reverse=True)[:25]: print(f"| {tool} | {role} | {tk} | {ap} | {f[-60:]} | {n} |")
print(f"\n({len(rr)} (thread,file) pairs with >3 reads across {len(set(x[4] for x in rr))} threads)")
# identical git diff / git log
print("\n## identical `git diff`/`git log`/`git status` commands re-run in a thread (>=3)\n| tool | role | ticket | thread | command | runs |\n|---|---|---|---|---|---|")
gg=[]
for tid,t in th.items():
    c=collections.Counter()
    for a in by.get(tid,[]):
        if isbash(a):
            for m in re.finditer(r"git (diff|log|status)[^;&|\n]*",a["cmd"]): c[m.group(0).strip()]+=1
    for k,n in c.items():
        if n>=3: gg.append((n,t["tool"],t["role"],t["ticket"],t["agent_path"][-30:],k))
for n,tool,role,tk,ap,k in sorted(gg,reverse=True)[:20]: print(f"| {tool} | {role} | {tk} | {ap} | `{k[:70]}` | {n} |")
print(f"\n({sum(x[0] for x in gg)} repeated invocations across {len(gg)} (thread,command) pairs)")
# read-gate reads
GATE=re.compile(r"(docs/decisions/\d{4}|AGENTS\.md|CLAUDE\.md|SKILL\.md|specs/PZL-TBD|TEAM-OPS\.md|design/04-backend-contract|docs/decisions/INDEX)")
print("\n## read-gate document reads per thread (ADRs, AGENTS/CLAUDE.md, SKILL.md, spec, TEAM-OPS, design/04)\n| tool | role | ticket | thread | gate reads | distinct gate docs | bytes returned | est. tokens (bytes/4) | thread total tok |\n|---|---|---|---|---|---|---|---|---|")
gate_rows=[]
for tid,t in th.items():
    A=[a for a in by.get(tid,[]) if (a["tool"]=="claude" and a["name"] in ("Read",) and GATE.search(a["cmd"])) or (isbash(a) and re.search(r"(sed -n|cat |head |rg |grep )",a["cmd"]) and GATE.search(a["cmd"]))]
    docs=set()
    for a in A:
        for m in GATE.finditer(a["cmd"]): docs.add(m.group(0))
    b=sum(int(a["out_len"] or 0) for a in A)
    if A: gate_rows.append((b,f'| {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["agent_path"][-30:]} | {len(A)} | {len(docs)} | {b/1e3:.0f}k | {b/4/1e3:.0f}k | {int(t["total_tokens"])/1e6:.1f}M |'))
for b,r in sorted(gate_rows,reverse=True)[:20]: print(r)
tb=sum(b for b,_ in gate_rows); print(f"\ntotal read-gate bytes returned across all threads: {tb/1e6:.1f} MB ≈ {tb/4/1e6:.1f}M tokens of tool-result text (each then re-read from cache on every later request in that thread); threads with gate reads: {len(gate_rows)}")
# ---- §2.7 orchestrator overhead
print("\n## §2.7 orchestrator overhead\n")
orch=[t for t in th.values() if t["role"]=="orchestrator" and int(t["total_tokens"])>1e6]
for t in orch:
    A=by.get(t["thread_id"],[])
    c=collections.Counter(a["name"] for a in A)
    waits=[a for a in A if a["name"]=="wait_agent"]
    wsec=sum(float(a["dur_s"] or 0) for a in waits)
    bash=[a for a in A if isbash(a)]
    prs=[a for a in bash if "gh pr create" in a["cmd"]]
    linear=[a for a in A if "linear" in a["name"].lower() or "linear" in a["cmd"].lower()]
    merge=[a for a in bash if re.search(r"git (merge|rebase|merge-tree|worktree add)",a["cmd"])]
    kids=[k for k in th.values() if k["parent_thread_id"]==t["thread_id"]]
    ktok=sum(int(k["total_tokens"]) for k in kids); kusd=sum(k["usd"] for k in kids)
    print(f'### {t["tool"]} {t["agent_path"] or t["thread_id"][:8]} ({t["model"]}/{t["effort"]})')
    print(f'- tokens {int(t["total_tokens"])/1e6:.1f}M (${t["usd"]:.0f}) vs children {ktok/1e6:.1f}M (${kusd:.0f}) → orchestrator share {100*int(t["total_tokens"])/max(1,int(t["total_tokens"])+ktok):.0f}% of tokens, {100*t["usd"]/max(1,t["usd"]+kusd):.0f}% of $; {len(kids)} direct children; API requests {t["api_requests"]}; output {int(t["output_tokens"])/1e3:.0f}k')
    print(f'- wall {int(t["wall_seconds"])/3600:.1f} h, active {int(t["active_seconds"])/3600:.1f} h, idle gaps>5m: {t["idle_gaps_over_5m"]} ({int(t["idle_minutes"])} min)')
    print(f'- tool calls: {dict(c.most_common(12))}')
    print(f'- wait_agent calls: {len(waits)}, cumulative wait {wsec/3600:.1f} h; bash {len(bash)}; gh pr create {len(prs)}; linear ops {len(linear)}; merge/worktree ops {len(merge)}')
    # checkpoint messages: final texts count
    print()
# ---- §2.8 idle & PR latency
print("## §2.8 idle gaps > 5 min (top threads by idle minutes)\n| tool | role | ticket | thread | wall min | active min | idle gaps | idle min | gaps (start, min) |\n|---|---|---|---|---|---|---|---|---|")
for t in sorted(th.values(),key=lambda t:-int(t["idle_minutes"]))[:16]:
    g=json.loads(t["gaps"]); print(f'| {t["tool"]} | {t["role"]} | {t["ticket"]} | {t["agent_path"][-30:]} | {int(t["wall_seconds"])//60} | {int(t["active_seconds"])//60} | {t["idle_gaps_over_5m"]} | {t["idle_minutes"]} | {"; ".join(f"{x[0][5:16]}Z+{x[1]}m" for x in g[:6])}{" …" if len(g)>6 else ""} |')
