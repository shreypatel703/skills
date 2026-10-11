import csv, re, json, collections
th={t["thread_id"]:t for t in json.load(open("threads_enriched.json"))}
acts=list(csv.DictReader(open("actions.csv")))
def isbash(a): return (a["tool"]=="codex" and a["kind"]=="exec") or (a["tool"]=="claude" and a["name"]=="Bash")
def full_runs(cmd):
    out=[]
    for m in re.finditer(r"\bmake (fe-)?test\b",cmd): out.append(m.group(0))
    for m in re.finditer(r"(?:uv run |python -m |timeout \d+ uv run )?pytest\b([^;|\n]*)",cmd):
        args=m.group(1); args=re.sub(r"\d?>\S*|&\s*$|&&.*$","",args)
        args=re.sub(r"-(k|p|o|m|W|n|x)\s+\S+","",args); args=re.sub(r"--\S+(=\S+)?","",args); args=re.sub(r"\s-\S+","",args)
        rest=[x for x in args.split() if x and not x.startswith("$") and x not in ("&&",)]
        if not rest: out.append("pytest(no path)")
    for m in re.finditer(r"pnpm (?:-C frontend )?(?:run )?test(?: --run)?\s*(?:$|[;&|>2])|pnpm vitest run\s*(?:$|[;&|>])|npx vitest run\s*(?:$|[;&|>])",cmd): out.append("vitest(all)")
    return out
rows=[]; per=collections.Counter()
for a in acts:
    if not isbash(a): continue
    fr=full_runs(a["cmd"])
    if fr:
        t=th[a["thread_id"]]; per[(t["tool"],t["role"],t["ticket"],t["agent_path"][-30:])]+=len(fr)
        rows.append((a["ts"],t["tool"],t["role"],t["ticket"],t["agent_path"][-30:],float(a["dur_s"] or 0),",".join(fr),a["cmd"][:110].replace("\n"," ")))
print(f"full-suite invocations: {len(rows)} in {len(per)} threads; total wall {sum(r[5] for r in rows)/60:.0f} min\n")
print("| tool | role | ticket | thread | full-suite runs |\n|---|---|---|---|---|")
for k,n in per.most_common(): print(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {n} |")
json.dump(rows,open("tables/t5_full_suite_runs.json","w"),indent=1)
print("\nby role:",collections.Counter(r[2] for r in rows))
print("longest:",sorted(rows,key=lambda r:-r[5])[:5])
