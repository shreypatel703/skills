"""Parse Codex rollouts touching the puzzle repo in the audit window.
Outputs: codex_threads.json, codex_events.csv (per token_count), codex_actions.csv (per tool call)."""
import json, os, glob, re, csv, datetime as dt, collections
home=os.path.expanduser("~")
import os
W0=os.environ.get("AUDIT_W0","2026-09-17T04:00:00Z"); W1=os.environ.get("AUDIT_W1","2026-09-18T22:15:00Z")   # UTC ISO bounds; set by audit.py
PUZ=re.compile(os.environ.get("AUDIT_CODEX_RE", r"^/Users/shrey/Documents/projects/puzzle"))
SECRET=re.compile(r"(lin_api_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]{8,}|eyJ[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|gAAAAA[A-Za-z0-9_-]{20,})")
def red(s): return SECRET.sub("<REDACTED>", s)
def pt(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
files=sorted(glob.glob(f"{home}/.codex/sessions/*/*/*/*.jsonl"))
threads={}; events=[]; actions=[]; skipped=[]
# pre-pass: per thread id, the set of cumulative token totals and call_ids, to strip replayed history from forked threads
CUMS={}; CALLS={}; FORK={}; TURNS={}
for f in files:
    tid=None
    for line in open(f):
        try: r=json.loads(line)
        except Exception: continue
        if r.get("type")=="session_meta" and tid is None:
            tid=r["payload"].get("id"); FORK[tid]=r["payload"].get("forked_from_id"); CUMS.setdefault(tid,set()); CALLS.setdefault(tid,set()); TURNS.setdefault(tid,set())
        elif r.get("type")=="turn_context": TURNS[tid].add(r["payload"].get("turn_id"))
        elif r.get("type")=="event_msg" and r["payload"].get("type")=="token_count" and r["payload"].get("info"):
            c=r["payload"]["info"].get("total_token_usage") or {}; CUMS[tid].add(c.get("total_tokens"))
        elif r.get("type")=="response_item" and r["payload"].get("type") in ("custom_tool_call","function_call"):
            CALLS[tid].add(r["payload"].get("call_id"))
for f in files:
    recs=[]
    bad=0
    with open(f) as fh:
        for line in fh:
            try: recs.append(json.loads(line))
            except Exception: bad+=1
    if not recs: skipped.append((f,"empty")); continue
    meta=recs[0]["payload"] if recs[0].get("type")=="session_meta" else {}
    cwd=meta.get("cwd","")
    if not PUZ.match(cwd): skipped.append((f,f"cwd={cwd}")); continue
    ts=[r["timestamp"] for r in recs if r.get("timestamp")]
    t0,t1=min(ts),max(ts)
    if (len(set(x[:19] for x in ts))<=3 or (pt(t1)-pt(t0)).total_seconds()<5) and len(recs)>10:
        skipped.append((f,f"imported history: {len(recs)} records all at {t0[:19]} (written in <5s)")); continue
    if t1<W0 or t0>W1: skipped.append((f,f"outside window {t0}..{t1}")); continue
    tid=meta.get("id")
    src=meta.get("source")
    parent=None; agent_path=meta.get("agent_path"); nick=meta.get("agent_nickname")
    if isinstance(src,dict) and "subagent" in src:
        sp=src["subagent"].get("thread_spawn",{})
        parent=sp.get("parent_thread_id"); agent_path=agent_path or sp.get("agent_path"); nick=nick or sp.get("agent_nickname")
    T=dict(thread_id=tid,file=f.replace(home,"~"),parent_thread_id=parent,agent_path=agent_path,nickname=nick,cwd=cwd,
           start_ts=t0,end_ts=t1,bad_lines=bad,models=collections.Counter(),efforts=collections.Counter(),turns=0,
           compactions=0,context_window=None,max_context_pct=0.0,rate_limit_events=0,
           final_total=None,children=[],branches=set(),cwds=set([cwd]),agent_messages=[],reasoning_blocks=0,
           in_window=dict(input=0,cached=0,cache_write=0,output=0,reasoning=0,total=0,events=0),
           all=dict(input=0,cached=0,cache_write=0,output=0,reasoning=0,total=0,events=0))
    model=effort=None; pending={}; last_cum=None
    src_id=meta.get("forked_from_id"); T["forked_from"]=src_id
    rep_cums=CUMS.get(src_id,set()) if src_id else set(); rep_calls=CALLS.get(src_id,set()) if src_id else set(); T["replayed_events"]=0
    for r in recs:
        t=r.get("timestamp"); ty=r.get("type"); p=r.get("payload",{})
        if ty=="turn_context":
            model=p.get("model"); effort=p.get("effort") or (p.get("collaboration_mode",{}).get("settings",{}) or {}).get("reasoning_effort")
            T["turns"]+=1; T["models"][model]+=1; T["efforts"][effort]+=1; T["cwds"].add(p.get("cwd"))
        elif ty in ("compacted",): T["compactions"]+=1
        elif ty=="event_msg":
            et=p.get("type")
            if et=="token_count" and p.get("info"):
                info=p["info"]; cum=info.get("total_token_usage") or {}; last=info.get("last_token_usage") or {}
                T["context_window"]=info.get("model_context_window") or T["context_window"]
                if T["context_window"] and last.get("input_tokens"):
                    T["max_context_pct"]=max(T["max_context_pct"], last["input_tokens"]/T["context_window"])
                keys=dict(input="input_tokens",cached="cached_input_tokens",cache_write="cache_write_input_tokens",
                       output="output_tokens",reasoning="reasoning_output_tokens",total="total_tokens")
                # attribute by cumulative delta (last_token_usage is occasionally re-emitted for the same response)
                if last_cum is None or cum.get("total_tokens",0) < last_cum.get("total_tokens",0):
                    d={k:cum.get(v,0) for k,v in keys.items()}
                else:
                    d={k:cum.get(v,0)-last_cum.get(v,0) for k,v in keys.items()}
                replayed = cum.get("total_tokens") in rep_cums and t[:19]==t0[:19]
                last_cum=cum
                if replayed: T["replayed_events"]+=1; continue
                if not any(d.values()): continue
                T["final_total"]=cum
                inw = W0<=t<=W1
                for k,v in d.items():
                    T["all"][k]+=v
                    if inw: T["in_window"][k]+=v
                T["all"]["events"]+=1
                if inw: T["in_window"]["events"]+=1
                rl=(p.get("rate_limits") or {}).get("rate_limit_reached_type")
                if rl: T["rate_limit_events"]+=1
                events.append(dict(tool="codex",thread_id=tid,ts=t,model=model,effort=effort,in_window=int(inw),**d))
            elif et in ("context_compacted","compacted"): pass  # counted once via the top-level `compacted` record
            elif et=="sub_agent_activity":
                if p.get("kind")=="started": T["children"].append((p.get("agent_thread_id"),p.get("agent_path")))
            elif et=="agent_message": T["agent_messages"].append((t,red(str(p.get("message",""))[:400])))
            elif et=="agent_reasoning": T["reasoning_blocks"]+=1
            elif et=="patch_apply_end":
                for m in re.finditer(r"^[AMD] (/\S+)$", p.get("stdout") or "", re.M): T.setdefault("files_edited",set()).add(m.group(1))
                T["patches"]=T.get("patches",0)+1
        elif ty=="response_item":
            rt=p.get("type")
            if p.get("call_id") in rep_calls: continue
            if rt=="custom_tool_call":
                inp=p.get("input") or ""
                m=re.search(r'"?cmd"?\s*:\s*"((?:[^"\\]|\\.)*)"',inp)
                cmd=json.loads('"'+m.group(1)+'"') if m else inp[:300]
                pending[p.get("call_id")]=(t,"exec",p.get("name"),cmd)
            elif rt=="function_call":
                args=p.get("arguments") or ""
                try: a=json.loads(args)
                except Exception: a={}
                summ=""
                if p.get("name")=="spawn_agent": summ=f"{a.get('task_name')} model={a.get('model')} effort={a.get('reasoning_effort')}"
                elif p.get("name") in ("wait_agent",): summ=f"timeout_ms={a.get('timeout_ms')}"
                elif p.get("name") in ("send_message","followup_task","interrupt_agent"):
                    summ=f"target={a.get('target') or a.get('task_name')}"
                    if p.get("name")=="interrupt_agent": T.setdefault("interrupted",[]).append((t,a.get('target') or a.get('task_name')))
                else: summ=red(args[:200])
                pending[p.get("call_id")]=(t,"function",p.get("name"),summ)
            elif rt in ("custom_tool_call_output","function_call_output"):
                cid=p.get("call_id"); st=pending.pop(cid,None)
                out=p.get("output"); out=out if isinstance(out,str) else json.dumps(out)
                if st:
                    t0_,kind,name,cmd=st
                    dur=(pt(t)-pt(t0_)).total_seconds()
                    m=re.search(r"Wall time ([0-9.]+) seconds",out or "")
                    wall=float(m.group(1)) if m else None
                    actions.append(dict(tool="codex",thread_id=tid,ts=t0_,kind=kind,name=name,cmd=red(cmd)[:500],dur_s=round(dur,1),wall_s=wall,
                                        out_len=len(out or ""),rc_hint=("429" in (out or "")[:2000]),in_window=int(W0<=t0_<=W1)))
            elif rt=="reasoning": pass
            elif rt=="message" and p.get("role")=="user":
                pass
    # git branch from exec commands
    for a in actions:
        if a["thread_id"]==tid:
            for m in re.finditer(r"(pzl-\d+-[a-z0-9-]+|integration/pzl-\d+-base|codex/[a-z0-9-]+)",a["cmd"]): T["branches"].add(m.group(1))
    T["models"]=dict(T["models"]); T["efforts"]=dict(T["efforts"]); T["branches"]=sorted(T["branches"]); T["cwds"]=sorted(x for x in T["cwds"] if x)
    T["files_edited"]=sorted(T.get("files_edited",set())); T["patches"]=T.get("patches",0); T["interrupted"]=T.get("interrupted",[])
    threads[tid]=T
json.dump(threads,open("codex_threads.json","w"),indent=1,default=str)
with open("codex_events.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=(list(events[0].keys()) if events else ['tool', 'thread_id', 'ts', 'model', 'effort', 'in_window', 'input', 'cached', 'cache_write', 'output', 'reasoning', 'total'])); w.writeheader(); w.writerows(events)
with open("codex_actions.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=(list(actions[0].keys()) if actions else ['tool', 'thread_id', 'ts', 'kind', 'name', 'cmd', 'dur_s', 'wall_s', 'out_len', 'rc_hint', 'in_window'])); w.writeheader(); w.writerows(actions)
with open("codex_skipped.txt","w") as o:
    for f,why in skipped: o.write(f"{f.replace(home,'~')}\t{why}\n")
print("threads",len(threads),"events",len(events),"actions",len(actions),"skipped",len(skipped))
# sanity: sum(last) vs final cumulative
bad=0
for tid,T in threads.items():
    ft=T["final_total"] or {}
    if ft and not T.get("forked_from") and abs(ft.get("total_tokens",0)-T["all"]["total"])>1000: bad+=1; print("MISMATCH",tid,T["agent_path"],ft.get("total_tokens"),T["all"]["total"])
print("mismatches",bad)
