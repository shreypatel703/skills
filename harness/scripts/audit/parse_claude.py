"""Parse Claude Code transcripts (main sessions + subagents) for the puzzle project in the audit window.
Outputs: claude_threads.json, claude_events.csv (per unique API request), claude_actions.csv (per tool call)."""
import json, os, glob, re, csv, datetime as dt, collections
home=os.path.expanduser("~")
import os
W0=os.environ.get("AUDIT_W0","2026-09-17T04:00:00Z"); W1=os.environ.get("AUDIT_W1","2026-09-18T22:15:00Z")   # UTC ISO bounds; set by audit.py
SELF_SESSION=os.environ.get("AUDIT_SELF_SESSION","")   # the session running the audit, if any
SECRET=re.compile(r"(lin_api_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]{8,}|eyJ[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,})")
def red(s): return SECRET.sub("<REDACTED>", s)
def pt(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
files=[]
import subprocess
_top=subprocess.run(["git","rev-parse","--show-toplevel"],capture_output=True,text=True).stdout.strip() or os.getcwd()
_top=os.environ.get("AUDIT_REPO",_top)
# Claude Code names a project dir by replacing "/" with "-" in the checkout path; worktrees are siblings with the same prefix
_prefix=os.path.dirname(_top).replace("/","-")+"-"+os.path.basename(_top).split("-")[0]
for proj in glob.glob(f"{home}/.claude/projects/{_prefix}*"):
    files+=glob.glob(f"{proj}/*.jsonl")+glob.glob(f"{proj}/*/subagents/*.jsonl")
threads={}; events=[]; actions=[]; skipped=[]
for f in sorted(files):
    if SELF_SESSION and SELF_SESSION in f: skipped.append((f,"this audit session")); continue
    recs=[]; bad=0
    with open(f) as fh:
        for line in fh:
            try: recs.append(json.loads(line))
            except Exception: bad+=1
    ts=[r["timestamp"] for r in recs if r.get("timestamp")]
    if not ts: skipped.append((f,"no timestamps")); continue
    t0,t1=min(ts),max(ts)
    if t1<W0 or t0>W1: skipped.append((f,f"outside window {t0[:16]}..{t1[:16]}")); continue
    m=re.search(r"subagents/agent-([0-9a-f]+)\.jsonl$",f)
    if m:
        tid="agent-"+m.group(1); parent=re.search(r"/([0-9a-f-]{36})/subagents/",f).group(1)
    else:
        tid=os.path.basename(f)[:-6]; parent=None
    T=dict(thread_id=tid,file=f.replace(home,"~"),parent_thread_id=parent,cwd=recs[0].get("cwd"),start_ts=t0,end_ts=t1,bad_lines=bad,
           models=collections.Counter(),efforts=collections.Counter(),turns=0,api_requests=0,compactions=0,rate_limit_events=0,
           title=None,first_prompt=None,branches=set(),cwds=set(),agent_spawns=[],resumes=0,
           in_window=dict(input=0,cached=0,cache_write=0,cache_write_1h=0,cache_write_5m=0,output=0,thinking=0,total=0,events=0),
           all=dict(input=0,cached=0,cache_write=0,cache_write_1h=0,cache_write_5m=0,output=0,thinking=0,total=0,events=0),
           max_context_tokens=0,final_texts=[])
    seen=set(); pending={}
    for r in recs:
        t=r.get("timestamp"); ty=r.get("type")
        if r.get("gitBranch"): T["branches"].add(r["gitBranch"])
        if r.get("cwd"): T["cwds"].add(r["cwd"])
        if ty=="custom-title": T["title"]=r.get("customTitle")
        elif ty=="user":
            c=r.get("message",{}).get("content")
            if isinstance(c,str):
                if T["first_prompt"] is None: T["first_prompt"]=red(c[:600])
                if not c.startswith("<task-notification>"): T["turns"]+=1
                if parent and T["turns"]>1 and not c.startswith("<task-notification>"): T["resumes"]+=1
            elif isinstance(c,list):
                for part in c:
                    if part.get("type")=="tool_result":
                        tr=r.get("toolUseResult")
                        if isinstance(tr,dict) and tr.get("agentId"): T.setdefault("agent_launches",[]).append(tr["agentId"])
                        cid=part.get("tool_use_id"); st=pending.pop(cid,None)
                        if st:
                            t0_,name,summ=st; out=part.get("content"); out=out if isinstance(out,str) else json.dumps(out)
                            actions.append(dict(tool="claude",thread_id=tid,ts=t0_,kind="tool",name=name,cmd=summ,dur_s=round((pt(t)-pt(t0_)).total_seconds(),1),
                                                wall_s=None,out_len=len(out or ""),rc_hint=("rate limit" in (out or "").lower()),in_window=int(W0<=t0_<=W1)))
                    elif part.get("type")=="text" and T["first_prompt"] is None: T["first_prompt"]=red(part["text"][:600])
        elif ty=="assistant":
            msg=r.get("message",{}); rid=r.get("requestId") or msg.get("id")
            for part in msg.get("content",[]) or []:
                if part.get("type")=="tool_use":
                    name=part.get("name"); inp=part.get("input",{}) or {}
                    if name=="Bash": summ=red(str(inp.get("command",""))[:500])
                    elif name in ("Read","Edit","Write","MultiEdit","NotebookEdit"): summ=str(inp.get("file_path",""))
                    elif name=="Agent":
                        summ=f"{inp.get('description')} model={inp.get('model')} bg={inp.get('run_in_background')} plen={len(inp.get('prompt') or '')}"
                        T["agent_spawns"].append(dict(ts=t,description=inp.get("description"),model=inp.get("model"),prompt_len=len(inp.get("prompt") or ""),prompt_head=red((inp.get("prompt") or "")[:300])))
                    elif name=="SendMessage": summ=f"to={inp.get('to')} len={len(str(inp.get('message') or ''))}"
                    elif name=="TaskStop":
                        summ=json.dumps(inp)[:200]; T.setdefault("interrupted",[]).append((t,inp.get("task_id") or inp.get("taskId") or summ))
                    elif name in ("Grep","Glob"): summ=f"{inp.get('pattern')} {inp.get('path') or ''}"
                    else: summ=red(json.dumps(inp)[:200])
                    pending[part.get("id")]=(t,name,summ)
                elif part.get("type")=="text":
                    txt=part.get("text","")
                    if "session limit" in txt or "rate limit" in txt.lower(): T["rate_limit_events"]+=1
                    T["final_texts"].append((t,red(txt[:300])))
            if rid in seen or not msg.get("usage"): continue
            seen.add(rid)
            u=msg["usage"]; cc=u.get("cache_creation") or {}
            d=dict(input=u.get("input_tokens",0),cached=u.get("cache_read_input_tokens",0),cache_write=u.get("cache_creation_input_tokens",0),
                   cache_write_1h=cc.get("ephemeral_1h_input_tokens",0),cache_write_5m=cc.get("ephemeral_5m_input_tokens",0),
                   output=u.get("output_tokens",0),thinking=(u.get("output_tokens_details") or {}).get("thinking_tokens",0))
            d["total"]=d["input"]+d["cached"]+d["cache_write"]+d["output"]
            ctx=d["input"]+d["cached"]+d["cache_write"]; T["max_context_tokens"]=max(T["max_context_tokens"],ctx)
            model=msg.get("model"); eff=r.get("effort")
            T["models"][model]+=1; T["efforts"][eff]+=1; T["api_requests"]+=1
            inw=W0<=t<=W1
            for k,v in d.items():
                T["all"][k]+=v
                if inw: T["in_window"][k]+=v
            T["all"]["events"]+=1
            if inw: T["in_window"]["events"]+=1
            events.append(dict(tool="claude",thread_id=tid,ts=t,model=model,effort=eff,in_window=int(inw),speed=u.get("speed"),tier=u.get("service_tier"),**d))
        elif ty=="system" and r.get("subtype") in ("compact_boundary","compaction"): T["compactions"]+=1
    T["models"]=dict(T["models"]); T["efforts"]=dict(T["efforts"]); T["branches"]=sorted(T["branches"]); T["cwds"]=sorted(T["cwds"])
    T["final_texts"]=T["final_texts"][-3:]; T["interrupted"]=T.get("interrupted",[])
    threads[tid]=T
json.dump(threads,open("claude_threads.json","w"),indent=1,default=str)
with open("claude_events.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=(list(events[0].keys()) if events else ['tool', 'thread_id', 'ts', 'model', 'effort', 'in_window', 'speed', 'tier', 'input', 'cached', 'cache_write', 'cache_write_1h', 'cache_write_5m', 'output', 'thinking', 'total'])); w.writeheader(); w.writerows(events)
with open("claude_actions.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=(list(actions[0].keys()) if actions else ['tool', 'thread_id', 'ts', 'kind', 'name', 'cmd', 'dur_s', 'wall_s', 'out_len', 'rc_hint', 'in_window'])); w.writeheader(); w.writerows(actions)
with open("claude_skipped.txt","w") as o:
    for f,why in skipped: o.write(f"{f.replace(home,'~')}\t{why}\n")
print("threads",len(threads),"events",len(events),"actions",len(actions),"skipped",len(skipped))
for tid,T in threads.items(): print(tid, T["start_ts"][11:16], T["end_ts"][11:16], T["models"], T["all"]["total"], T["turns"], (T["title"] or T["first_prompt"] or "")[:80].replace("\n"," "))
