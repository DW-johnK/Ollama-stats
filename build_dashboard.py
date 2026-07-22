#!/usr/bin/env python3
"""
Build the Open Ollama dashboard HTML from scraped data.
Combines the Ollama API data with browser-scraped metadata.
"""
import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# Load browser-scraped rich data (233 models with pulls, descriptions, capabilities)
rich_path = os.path.join(DATA_DIR, 'ollama_rich_models.json')
if os.path.exists(rich_path):
    with open(rich_path) as f:
        rich_data = json.load(f)
else:
    rich_data = []

# Load API data (342 models with sizes, digests)
api_path = os.path.join(DATA_DIR, 'ollama_models.json')
if os.path.exists(api_path):
    with open(api_path) as f:
        api_data = json.load(f)
else:
    api_data = []

# Build lookup from API data for sizes
api_sizes = {}
for m in api_data:
    name = m.get('name', m.get('model', '')).split(':')[0]
    size_bytes = m.get('size', 0)
    size_gb = round(size_bytes / (1024**3), 2) if size_bytes else 0
    if name not in api_sizes or size_gb > api_sizes[name].get('size_gb', 0):
        api_sizes[name] = {'size_bytes': size_bytes, 'size_gb': size_gb}

# Build the final merged dataset
# Priority: browser data (has pulls, descriptions, capabilities) -> API data (has sizes)
all_models = []
seen = set()

# First add all browser-scraped models (rich data)
for m in rich_data:
    name = m['name']
    if name in seen:
        continue
    seen.add(name)
    
    # Merge size from API data
    size_gb = api_sizes.get(name, {}).get('size_gb', 0)
    
    all_models.append({
        'name': name,
        'owner': m.get('owner', name.split('-')[0].title()),
        'description': m.get('description', ''),
        'pulls': m.get('pulls', 0),
        'pullsDisplay': m.get('pullsDisplay', '0'),
        'tagsCount': m.get('tagsCount', 0),
        'capabilities': m.get('capabilities', []),
        'sizes': m.get('sizes', []),
        'size_gb': size_gb,
        'updated': m.get('updated', ''),
    })

# Add any API models not in browser data
for m in api_data:
    name = m.get('name', m.get('model', '')).split(':')[0]
    if name in seen:
        continue
    seen.add(name)
    size_bytes = m.get('size', 0)
    size_gb = round(size_bytes / (1024**3), 2) if size_bytes else 0
    
    # Infer owner from name
    owner = name.split('-')[0].title()
    owner_map = {
        'deepseek': 'DeepSeek', 'llama': 'Meta', 'gemma': 'Google DeepMind',
        'qwen': 'Alibaba Cloud', 'mistral': 'Mistral AI', 'glm': 'Zhipu AI',
        'kimi': 'Moonshot AI', 'minimax': 'MiniMax', 'nemotron': 'NVIDIA',
        'phi': 'Microsoft', 'gpt': 'OpenAI', 'granite': 'IBM', 'gemma4': 'Google DeepMind',
    }
    for prefix, mapped in owner_map.items():
        if name.lower().startswith(prefix):
            owner = mapped
            break
    
    all_models.append({
        'name': name,
        'owner': owner,
        'description': '',
        'pulls': 0,
        'pullsDisplay': '0',
        'tagsCount': 0,
        'capabilities': [],
        'sizes': [],
        'size_gb': size_gb,
        'updated': m.get('modified_at', ''),
    })

# Sort by pulls descending
all_models.sort(key=lambda x: x['pulls'], reverse=True)

# Generate the HTML
html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Open Ollama — Model Explorer & Comparator</title>
<style>
:root{--bg:#0a0e1a;--surface:#111827;--surface2:#1e293b;--border:#1e3a5f;--text:#e2e8f0;--muted:#64748b;--accent:#6366f1;--accent2:#a855f7;--green:#10b981}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{background:linear-gradient(135deg,#1e1b4b,#312e81,#4c1d95);padding:40px 20px 30px;border-bottom:1px solid var(--border)}
.header h1{font-size:2.5rem;font-weight:800;background:linear-gradient(to right,#818cf8,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center}
.header p{text-align:center;color:var(--muted);font-size:1.05rem;margin-top:8px}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;max-width:1400px;margin:24px auto;padding:0 20px}
.stat-box{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:20px;text-align:center}
.stat-val{font-size:2rem;font-weight:800;color:white}.stat-label{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.controls{max-width:1400px;margin:0 auto;padding:12px 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.search-box{flex:1;min-width:220px;padding:10px 16px;background:var(--surface);border:1px solid var(--border);border-radius:10px;color:white;font-size:.95rem;outline:none}
.search-box:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(99,102,241,.2)}
select{padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:10px;color:white;font-size:.9rem;cursor:pointer}
.cap-btn{padding:7px 14px;background:var(--surface);border:1px solid var(--border);border-radius:10px;color:var(--muted);font-size:.8rem;font-weight:600;cursor:pointer;transition:all .2s}
.cap-btn.active{color:white}.cap-btn.vision.active{background:#7c3aed;border-color:#7c3aed}.cap-btn.tools.active{background:#0891b2;border-color:#0891b2}
.cap-btn.thinking.active{background:#d97706;border-color:#d97706}.cap-btn.audio.active{background:#db2777;border-color:#db2777}
.cap-btn.cloud.active{background:#2563eb;border-color:#2563eb}.cap-btn.embedding.active{background:#059669;border-color:#059669}
.owner-section{max-width:1400px;margin:0 auto;padding:0 20px 16px}
.owner-header{display:flex;align-items:center;gap:10px;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
.owner-name{font-size:1.15rem;font-weight:700;color:white}.owner-count{font-size:.78rem;color:var(--muted);background:var(--surface2);padding:2px 8px;border-radius:12px}
.model-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.mc{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px;transition:all .2s;position:relative}
.mc:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 30px rgba(99,102,241,.12)}
.mc .name{font-size:1.05rem;font-weight:700;color:white;margin-bottom:4px;font-family:'SF Mono',Monaco,Consolas,monospace}
.mc .desc{font-size:.78rem;color:var(--muted);line-height:1.35;margin-bottom:10px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.mr{display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:4px}.mr .l{color:var(--muted)}.mr .v{font-weight:600;color:var(--text)}
.pb{height:3px;background:var(--surface2);border-radius:2px;margin-top:6px;overflow:hidden}.pf{height:100%;background:linear-gradient(to right,var(--accent),var(--accent2));border-radius:2px}
.tags{display:flex;flex-wrap:wrap;gap:3px;margin-top:8px}
.tag{font-size:.65rem;padding:2px 7px;border-radius:5px;font-weight:600;text-transform:uppercase}
.tag.vision{background:#7c3aed33;color:#a78bfa}.tag.tools{background:#0891b233;color:#22d3ee}.tag.thinking{background:#d9770633;color:#fbbf24}
.tag.audio{background:#db277733;color:#f472b6}.tag.cloud{background:#2563eb33;color:#60a5fa}.tag.embedding{background:#05966933;color:#34d399}
.st{background:var(--surface2);color:#94a3b8;font-size:.65rem;padding:2px 5px;border-radius:3px;font-family:monospace}
.copy-btn{position:absolute;top:14px;right:14px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:3px 8px;font-size:.7rem;color:var(--muted);cursor:pointer;transition:all .2s}
.copy-btn:hover{background:var(--accent);color:white;border-color:var(--accent)}
.no-results{text-align:center;padding:60px 20px;color:var(--muted);font-size:1.2rem}
</style>
</head>
<body>
<div class="header">
<h1>🦙 Open Ollama — Model Explorer</h1>
<p>''' + str(len(all_models)) + ''' models · ''' + str(len(set(m['owner'] for m in all_models))) + ''' owners · Filter, search, compare & copy pull commands</p>
</div>
<div class="stats-row" id="statsRow"></div>
<div class="controls">
<input class="search-box" id="search" placeholder="Search by name, owner, or description..." oninput="render()">
<select id="sortSelect" onchange="render()">
<option value="pulls_desc">Most Popular</option>
<option value="pulls_asc">Least Popular</option>
<option value="name_asc">Name A→Z</option>
<option value="name_desc">Name Z→A</option>
<option value="tags_desc">Most Tags</option>
<option value="updated_desc">Newest First</option>
</select>
<button class="cap-btn vision" data-cap="vision" onclick="toggleCap(this)">👁 Vision</button>
<button class="cap-btn tools" data-cap="tools" onclick="toggleCap(this)">🔧 Tools</button>
<button class="cap-btn thinking" data-cap="thinking" onclick="toggleCap(this)">🧠 Thinking</button>
<button class="cap-btn audio" data-cap="audio" onclick="toggleCap(this)">🎤 Audio</button>
<button class="cap-btn cloud" data-cap="cloud" onclick="toggleCap(this)">☁️ Cloud</button>
<button class="cap-btn embedding" data-cap="embedding" onclick="toggleCap(this)">📊 Embed</button>
</div>
<div id="content"></div>
<script>
const MODELS=''' + json.dumps(all_models) + ''';
const MAX_PULLS=Math.max(...MODELS.map(m=>m.pulls));
let activeCaps=new Set();
function toggleCap(btn){const c=btn.dataset.cap;btn.classList.toggle('active');if(activeCaps.has(c))activeCaps.delete(c);else activeCaps.add(c);render();}
function render(){
  const q=document.getElementById('search').value.toLowerCase();
  const sort=document.getElementById('sortSelect').value;
  let filtered=MODELS.filter(m=>{
    const ms=!q||m.name.toLowerCase().includes(q)||m.owner.toLowerCase().includes(q)||m.description.toLowerCase().includes(q);
    const mc=[...activeCaps].every(c=>m.capabilities.includes(c));
    return ms&&mc;
  });
  filtered.sort((a,b)=>{
    if(sort==='pulls_desc')return b.pulls-a.pulls;
    if(sort==='pulls_asc')return a.pulls-b.pulls;
    if(sort==='name_asc')return a.name.localeCompare(b.name);
    if(sort==='name_desc')return b.name.localeCompare(a.name);
    if(sort==='tags_desc')return b.tagsCount-a.tagsCount;
    return 0;
  });
  const tp=MODELS.reduce((s,m)=>s+m.pulls,0);
  const uo=[...new Set(MODELS.map(m=>m.owner))].length;
  const uc=[...new Set(MODELS.flatMap(m=>m.capabilities))].filter(Boolean).length;
  document.getElementById('statsRow').innerHTML=
    `<div class="stat-box"><div class="stat-val">${MODELS.length}</div><div class="stat-label">Models</div></div>`+
    `<div class="stat-box"><div class="stat-val">${uo}</div><div class="stat-label">Owners</div></div>`+
    `<div class="stat-box"><div class="stat-val">${(tp/1e6).toFixed(0)}M</div><div class="stat-label">Total Pulls</div></div>`+
    `<div class="stat-box"><div class="stat-val">${uc}</div><div class="stat-label">Capabilities</div></div>`;
  const byOwner={};
  filtered.forEach(m=>{if(!byOwner[m.owner])byOwner[m.owner]=[];byOwner[m.owner].push(m);});
  const oo=Object.entries(byOwner).sort((a,b)=>b[1].reduce((s,m)=>s+m.pulls,0)-a[1].reduce((s,m)=>s+m.pulls,0));
  if(!filtered.length){document.getElementById('content').innerHTML='<div class="no-results">No models match your filters</div>';return;}
  let html='';
  oo.forEach(([owner,models])=>{
    html+=`<div class="owner-section"><div class="owner-header"><span class="owner-name">${owner}</span><span class="owner-count">${models.length}</span></div><div class="model-grid">`;
    models.forEach(m=>{
      const pp=MAX_PULLS>0?(m.pulls/MAX_PULLS*100):0;
      const caps=m.capabilities.map(c=>`<span class="tag ${c}">${c}</span>`).join('');
      const sizes=m.sizes.map(s=>`<span class="st">${s}</span>`).join('');
      html+=`<div class="mc">
        <button class="copy-btn" onclick="navigator.clipboard.writeText('ollama pull ${m.name}')">📋 Pull</button>
        <div class="name">${m.name}</div>
        <div class="desc">${m.description||'No description available'}</div>
        <div class="mr"><span class="l">Pulls</span><span class="v" style="color:var(--green)">${m.pullsDisplay}</span></div>
        <div class="mr"><span class="l">Updated</span><span class="v">${m.updated||'N/A'}</span></div>
        <div class="mr"><span class="l">Tags</span><span class="v">${m.tagsCount}</span></div>
        <div class="pb"><div class="pf" style="width:${pp}%"></div></div>
        <div class="tags">${caps}${sizes}</div>
      </div>`;
    });
    html+='</div></div>';
  });
  document.getElementById('content').innerHTML=html;
}
render();
</script>
</body>
</html>'''

output_path = os.path.join(DATA_DIR, 'index.html')
with open(output_path, 'w') as f:
    f.write(html)

print(f"Dashboard generated at {output_path}")
print(f"Total models: {len(all_models)}")
print(f"Unique owners: {len(set(m['owner'] for m in all_models))}")
print(f"Top 5 owners:")
from collections import Counter
owner_counts = Counter(m['owner'] for m in all_models)
for owner, count in owner_counts.most_common(5):
    print(f"  {owner}: {count} models")