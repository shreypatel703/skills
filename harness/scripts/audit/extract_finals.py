"""Dump each thread's final agent message(s) to finals/<thread>.md (redacted) and count blocker mentions."""
import json, os, re, glob, csv
home=os.path.expanduser("~")
SECRET=re.compile(r"(lin_api_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]{8,}|eyJ[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|gAAAAA[A-Za-z0-9_-]{20,})")
red=lambda s:SECRET.sub("<REDACTED>",s)
os.makedirs("finals",exist_ok=True)
rows=list(csv.DictReader(open("threads.csv"))) if __import__("os").path.exists("threads.csv") else []
cx=json.load(open("codex_threads.json")); cl=json.load(open("claude_threads.json"))
out=[]
for r in rows:
    tid=r["thread_id"]; msgs=[]
    if r["tool"]=="codex":
        f=cx[tid]["file"].replace("~",home)
        for line in open(f):
            try: rec=json.loads(line)
            except: continue
            if rec.get("type")=="event_msg" and rec["payload"].get("type")=="agent_message":
                msgs.append((rec["timestamp"],rec["payload"].get("message","")))
    else:
        f=cl[tid]["file"].replace("~",home)
        for line in open(f):
            try: rec=json.loads(line)
            except: continue
            if rec.get("type")=="assistant":
                for p in rec.get("message",{}).get("content",[]) or []:
                    if p.get("type")=="text" and len(p.get("text",""))>200: msgs.append((rec["timestamp"],p["text"]))
    txt="\n\n---\n\n".join(f"[{t}]\n{red(m)}" for t,m in msgs)
    open(f"finals/{tid}.md","w").write(txt)
    last=red(msgs[-1][1]) if msgs else ""
    blockers=len(re.findall(r"\bBLOCKER",last))
    # count numbered blocker items in headings like "BLOCKERS (n)" or "N blockers"
    m=re.search(r"(\d+)\s+blockers?\b",last,re.I); n_stated=int(m.group(1)) if m else None
    m2=re.search(r"BLOCKERS?\s*[:(]\s*(\d+)",last); n_stated2=int(m2.group(1)) if m2 else None
    out.append(dict(thread_id=tid,role=r["role"],ticket=r["ticket"],agent_path=r["agent_path"],n_msgs=len(msgs),last_len=len(last),blocker_mentions=blockers,stated_blockers=n_stated if n_stated is not None else n_stated2,
                    verdict_hint=("CLEAN" if re.search(r"\b(no blockers|0 blockers|clean)\b",last,re.I) else ""), last_head=last[:200].replace("\n"," ")))
if not out: print("no threads"); raise SystemExit(0)
with open("finals_index.csv","w") as o:
    w=csv.DictWriter(o,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
for o in out:
    if o["role"]=="reviewer": print(f'{o["ticket"]:8} {o["agent_path"][-40:]:40} msgs={o["n_msgs"]:3} len={o["last_len"]:6} BLOCKER={o["blocker_mentions"]:2} stated={o["stated_blockers"]} {o["verdict_hint"]:5} {o["last_head"][:100]}')
