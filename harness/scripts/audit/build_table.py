"""Merge codex + claude threads into the normalized event table (threads.csv) and per-action table (actions.csv)."""
import json, csv, re, collections, datetime as dt
def pt(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
cx=json.load(open("codex_threads.json")); cl=json.load(open("claude_threads.json"))
acts=list(csv.DictReader(open("codex_actions.csv")))+list(csv.DictReader(open("claude_actions.csv")))
ev_by_thread=collections.defaultdict(list)
for e in list(csv.DictReader(open("codex_events.csv")))+list(csv.DictReader(open("claude_events.csv"))): ev_by_thread[e["thread_id"]].append(e)
by_thread=collections.defaultdict(list)
for a in acts: by_thread[a["thread_id"]].append(a)
# Claude: agentId -> spawn description (from parent)
desc={}
for tid,T in cl.items():
    for sp in T["agent_spawns"]: pass
for T in cl.values():  # map each spawned agent id to its Agent-tool spawn (same order as the async_launched results)
    for aid,sp in zip(T.get("agent_launches",[]),T.get("agent_spawns",[])): desc["agent-"+aid]=sp
TEST=re.compile(r"\b(pytest|vitest|pnpm (run )?test|make (fe-)?test|uv run pytest)\b")
FULL=re.compile(r"(^|[;&|]\s*)(uv run )?pytest(\s+-q)?(\s+-x)?(\s+-p\s+\S+)?\s*($|[;&|>])|make test\b|pnpm (run )?test\s*($|[;&|>])|make fe-test|npx vitest run\s*($|[;&|])|pnpm vitest run\s*($|[;&|])")
READ=re.compile(r"\b(sed -n|cat|head|tail|rg|grep|ls|bat)\b")
def role_of(tool,T,d):
    if tool=="codex":
        ap=(T.get("agent_path") or "")
        if not T.get("parent_thread_id") or ap in ("/root","") or ap.endswith("orchestrator"): return "orchestrator"
        leaf=ap.split("/")[-1]
        if "review" in leaf or "standards" in leaf or "spec" in leaf or "axis" in leaf: return "reviewer"
        if "impl" in leaf or "rewrite" in leaf or "fix" in leaf: return "implementer"
        return "other"
    else:
        if not T.get("parent_thread_id"): return "orchestrator"
        fp=(T.get("first_prompt") or "").lower(); ds=(d or {}).get("description","").lower()
        if "merge" in ds or "resolving an in-progress git merge" in fp: return "merge"
        if "review" in ds or "code-review subagent" in fp: return "reviewer"
        if "implement" in ds or "implementation subagent" in fp or "targeted fix" in fp: return "implementer"
        return "other"
def ticket_of(tool,T,d):
    s=" ".join([(T.get("agent_path") or ""),(d or {}).get("description",""),(T.get("first_prompt") or "")[:200]," ".join(T.get("branches",[]))," ".join(T.get("cwds",[]))])
    m=re.search(r"pzl[_-]?(\d{2,3})",s,re.I)
    if role_of(tool,T,d)=="orchestrator": return "(orchestrator)"
    return f"PZL-{m.group(1)}" if m else "?"
rows=[]
for tool,src in (("codex",cx),("claude",cl)):
    for tid,T in src.items():
        d=desc.get(tid)
        A=by_thread.get(tid,[])
        tc=collections.Counter(a["name"] for a in A)
        bash=[a for a in A if (tool=="codex" and a["kind"]=="exec") or (tool=="claude" and a["name"]=="Bash")]
        reads=set()
        for a in A:
            if tool=="claude" and a["name"]=="Read": reads.add(a["cmd"])
            elif (tool=="codex" and a["kind"]=="exec") or (tool=="claude" and a["name"]=="Bash"):
                for m in re.finditer(r"(?:sed -n '[^']*' |cat |head [^|]*?|rg -n [^|]*? )([\w./-]+\.(?:py|md|ts|tsx|json|toml|yml|yaml|sh|css))",a["cmd"]): reads.add(m.group(1))
        edits=set()
        if tool=="claude":
            for a in A:
                if a["name"] in ("Edit","Write","MultiEdit"): edits.add(a["cmd"])
        else: edits=set(T.get("files_edited",[]))
        commits=sum(1 for a in bash if re.search(r"\bgit\b[^;&|\n]*\bcommit\b",a["cmd"]))
        amends=sum(1 for a in bash if re.search(r"\bgit\b[^;&|\n]*\bcommit\b[^;&|\n]*--amend",a["cmd"]))
        tests=[a for a in bash if TEST.search(a["cmd"])]
        full=[a for a in tests if FULL.search(a["cmd"])]
        test_secs=sum(float(a["dur_s"] or 0) for a in tests)
        w=T["in_window"]; al=T["all"]
        tsl=sorted(set([T["start_ts"],T["end_ts"]]+[a["ts"] for a in A]+[e["ts"] for e in ev_by_thread.get(tid,[])]))
        gaps=[]; active=0.0
        for i in range(1,len(tsl)):
            g=(pt(tsl[i])-pt(tsl[i-1])).total_seconds()
            if g>300: gaps.append((tsl[i-1],round(g/60)))
            else: active+=g
        big_gaps=gaps
        wall=(pt(T["end_ts"])-pt(T["start_ts"])).total_seconds()
        models="+".join(sorted(k for k in T["models"] if k and not k.startswith("<")))
        efforts="+".join(sorted(str(k) for k in T["efforts"] if k))
        rl=T.get("rate_limit_events",0)
        outcome="rate-limited" if rl else "clean"
        rows.append(dict(tool=tool,thread_id=tid,parent_thread_id=T.get("parent_thread_id") or "",agent_path=T.get("agent_path") or (d or {}).get("description","") or (T.get("title") or ""),
            role=role_of(tool,T,d),ticket=ticket_of(tool,T,d),model=models,effort=efforts,start_ts=T["start_ts"],end_ts=T["end_ts"],wall_seconds=int(wall),active_seconds=int(active),idle_gaps_over_5m=len(big_gaps),idle_minutes=sum(g[1] for g in big_gaps),gaps=json.dumps(big_gaps),
            turns=T.get("turns",0),api_requests=T.get("api_requests") or al["events"],
            input_tokens=al["input"] if tool=="claude" else al["input"]-al["cached"],  # fresh (uncached) input
            cached_input_tokens=al["cached"],cache_write_tokens=al["cache_write"],cache_write_1h=al.get("cache_write_1h",0),cache_write_5m=al.get("cache_write_5m",0),
            output_tokens=al["output"],thinking_tokens=al.get("thinking",al.get("reasoning",0)),total_tokens=al["total"],
            in_window_total=w["total"],
            tool_calls=json.dumps(dict(tc.most_common())),n_tool_calls=len(A),bash_commands=len(bash),files_read=len(reads),files_edited=len(edits),
            commits_produced=commits,amends=amends,test_runs=len(tests),full_suite_runs=len(full),test_wall_s=int(test_secs),
            compactions=T.get("compactions",0),max_context_pct=round(T.get("max_context_pct",0)*100,1) if tool=="codex" else round(T.get("max_context_tokens",0)/1000000*100,1),
            rate_limit_events=rl,interrupted_by_parent=0,outcome=outcome,resumes=T.get("resumes",0) if tool=="claude" else max(0,T.get("turns",0)-1)))
# interrupted flags
for tid,T in list(cx.items())+list(cl.items()):
    for t,target in T.get("interrupted",[]):
        for r in rows:
            if (r["tool"]=="codex" and (r["agent_path"]==target or r["agent_path"].endswith("/"+str(target)))) or (r["tool"]=="claude" and r["thread_id"]=="agent-"+str(target)):
                r["interrupted_by_parent"]+=1; r["outcome"]="killed" if r["outcome"]=="clean" else r["outcome"]
rows.sort(key=lambda r:r["start_ts"])
if not rows: print("no threads in window"); raise SystemExit(0)
with open("threads.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with open("actions.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=(list(acts[0].keys()) if acts else ["tool","thread_id","ts","kind","name","cmd","dur_s","wall_s","out_len","rc_hint","in_window"])); w.writeheader(); w.writerows(acts)
print(len(rows),"threads")
for r in rows: print(f'{r["tool"]:6} {r["role"]:12} {r["ticket"]:8} {r["model"]:16} {r["start_ts"][5:16]} {r["wall_seconds"]//60:5}m tot={r["total_tokens"]/1e6:7.1f}M out={r["output_tokens"]/1e3:6.0f}k think={r["thinking_tokens"]/1e3:6.0f}k calls={r["n_tool_calls"]:4} tests={r["test_runs"]:3}/{r["full_suite_runs"]} commits={r["commits_produced"]} {r["outcome"]:12} {r["agent_path"][:45]}')
