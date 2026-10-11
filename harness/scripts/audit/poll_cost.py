import json, os, collections
from analyze1 import cost
home=os.path.expanduser("~")
files={"main orchestrator (01a0ad84)":"~/.codex/sessions/2026/09/16/rollout-2026-09-16T23-59-00-01a0ad84-8d87-7893-a3ce-9e1de750e02f.jsonl",
       "parallel_wave_orchestrator":"~/.codex/sessions/2026/09/18/rollout-2026-09-18T00-15-21-01a0b2b9-e00d-7b31-b414-e3d89b79a26b.jsonl"}
for name,f in files.items():
    calls=[]; last=None; agg=collections.defaultdict(lambda:collections.Counter()); waits=[]
    for line in open(f.replace("~",home)):
        r=json.loads(line); p=r.get("payload",{})
        if r["type"]=="response_item" and p.get("type")=="function_call":
            calls.append(p["name"])
            if p["name"]=="wait_agent":
                try: waits.append(json.loads(p.get("arguments") or "{}").get("timeout_ms"))
                except: pass
        elif r["type"]=="response_item" and p.get("type")=="custom_tool_call": calls.append("exec")
        elif r["type"]=="response_item" and p.get("type")=="message" and p.get("role")=="assistant": calls.append("message")
        elif r["type"]=="event_msg" and p.get("type")=="token_count" and p.get("info"):
            cum=p["info"]["total_token_usage"]
            if last is None: last=cum; calls=[]; continue
            d={k:cum[k]-last[k] for k in cum}; last=cum
            if d["total_tokens"]<=0: calls=[]; continue
            kind="poll" if calls and all(c in ("wait_agent","list_agents") for c in calls) else ("none" if not calls else "work")
            a=agg[kind]; a["n"]+=1; a["tok"]+=d["total_tokens"]; a["out"]+=d["output_tokens"]
            a["usd"]+=cost("gpt-5.6-sol",d["input_tokens"]-d["cached_input_tokens"],d["cached_input_tokens"],0,0,d["output_tokens"])
            calls=[]
    print(f"### {name}")
    for k,a in agg.items(): print(f"- {k}: {a['n']} responses, {a['tok']/1e6:.1f}M tokens, {a['out']/1e3:.0f}k output, ${a['usd']:.0f}")
    c=collections.Counter(waits); print(f"- wait_agent timeout_ms distribution: {dict(sorted(c.items(), key=lambda kv:-kv[1])[:8])}")
