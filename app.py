#!/usr/bin/env python3
"""
Ollama Model Dashboard - Interactive Explorer & Analyzer
A high-performance dashboard for discovering and comparing AI models from Ollama.
"""

import json
import os
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Constants
DATA_FILE = '/Users/johnkalfayan/Developer/Open_Ollama/ollama_models.json'
PORT = 5000

def load_models():
    """Load and clean model data from the JSON store"""
    if not os.path.exists(DATA_FILE):
        return []
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Deduplicate by digest and add custom organization logic
    seen = set()
    unique = []
    for m in data:
        digest = m.get('digest')
        if digest and digest not in seen:
            seen.add(digest)
            # Extract owner from name (e.g., "llama3:8b" -> "Llama3")
            name = m.get('name', 'unknown')
            owner = name.split(':')[0].split('-')[0].title()
            
            unique.append({
                'name': name,
                'owner': owner,
                'size_gb': round(m.get('size', 0) / (1024**3), 2),
                'pulls': int(m.get('pull_count', 0)),
                'modified': m.get('modified_at', 'Unknown'),
                'digest': digest
            })
    return unique

@app.route('/')
def index():
    models = load_models()
    total_models = len(models)
    total_size = sum(m['size_gb'] for m in models)
    total_pulls = sum(m['pulls'] for m in models)
    
    # Single-file HTML implementation for zero-dependency deployment
    template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Open Ollama Explorer</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #6366f1; --secondary: #a855f7; --accent: #ec4899;
                --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --text-muted: #94a3b8;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
            body { background-color: var(--bg); color: var(--text); min-height: 100vh; padding: 40px 20px; }
            .container { max-width: 1400px; margin: 0 auto; }
            
            header { text-align: center; margin-bottom: 50px; }
            h1 { font-size: 3.5rem; font-weight: 800; background: linear-gradient(to right, #818cf8, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
            .subtitle { font-size: 1.2rem; color: var(--text-muted); }
            
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 40px; }
            .stat-card { background: var(--card); padding: 24px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); text-align: center; }
            .stat-value { font-size: 2.5rem; font-weight: 800; color: white; margin-bottom: 5px; }
            .stat-label { color: var(--text-muted); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
            
            .toolbar { display: flex; gap: 15px; margin-bottom: 30px; justify-content: center; flex-wrap: wrap; }
            input, select { 
                background: var(--card); color: white; border: 1px solid rgba(255,255,255,0.1); 
                padding: 12px 20px; border-radius: 12px; font-size: 1rem; outline: none;
            }
            input:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2); }
            
            .models-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
            .model-card { 
                background: var(--card); border-radius: 24px; padding: 24px; 
                border: 1px solid rgba(255,255,255,0.05); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                cursor: pointer; position: relative;
            }
            .model-card:hover { transform: translateY(-8px); border-color: var(--primary); box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
            .owner-tag { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--primary); margin-bottom: 8px; display: block; }
            .model-name { font-size: 1.4rem; font-weight: 700; margin-bottom: 15px; display: block; color: white; }
            
            .metric { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.9rem; }
            .metric-label { color: var(--text-muted); }
            .metric-value { font-weight: 600; color: #e2e8f0; }
            
            .pull-btn { 
                width: 100%; margin-top: 20px; padding: 12px; border-radius: 12px; border: none;
                background: linear-gradient(to right, var(--primary), var(--secondary));
                color: white; font-weight: 600; cursor: pointer; transition: opacity 0.2s;
            }
            .pull-btn:hover { opacity: 0.9; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Open Ollama Explorer</h1>
                <p class="subtitle">Analyze, Compare, and Discover the most popular local LLMs</p>
            </header>
            
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-value">{{ total_models }}</div><div class="stat-label">Unique Models</div></div>
                <div class="stat-card"><div class="stat-value">{{ "%.1f"|format(total_size) }} GB</div><div class="stat-label">Combined Size</div></div>
                <div class="stat-card"><div class="stat-value">{{ "{:,}".format(total_pulls) }}</div><div class="stat-label">Total Pulls</div></div>
            </div>
            
            <div class="toolbar">
                <input type="text" id="search" placeholder="Search models or owners..." oninput="filterModels()">
                <select id="sort" onchange="filterModels()">
                    <option value="pulls_desc">Most Popular</option>
                    <option value="size_asc">Smallest Size</option>
                    <option value="size_desc">Largest Size</option>
                </select>
            </div>
            
            <div class="models-grid" id="grid"></div>
        </div>
        
        <script>
            const models = {{ models_json | safe }};
            
            function render(data) {
                const grid = document.getElementById('grid');
                grid.innerHTML = data.map(m => `
                    <div class="model-card">
                        <span class="owner-tag">${m.owner}</span>
                        <span class="model-name">${m.name}</span>
                        <div class="metric">
                            <span class="metric-label">Size</span>
                            <span class="metric-value">${m.size_gb} GB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Pulls</span>
                            <span class="metric-value">${m.pulls.toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Modified</span>
                            <span class="metric-value">${m.modified}</span>
                        </div>
                        <button class="pull-btn" onclick="alert('ollama pull ${m.name}')">🔗 Copy Pull Command</button>
                    </div>
                `).join('');
            }
            
            function filterModels() {
                const q = document.getElementById('search').value.toLowerCase();
                const sort = document.getElementById('sort').value;
                
                let filtered = models.filter(m => 
                    m.name.toLowerCase().includes(q) || m.owner.toLowerCase().includes(q)
                );
                
                if (sort === 'pulls_desc') filtered.sort((a,b) => b.pulls - a.pulls);
                if (sort === 'size_asc') filtered.sort((a,b) => a.size_gb - b.size_gb);
                if (sort === 'size_desc') filtered.sort((a,b) => b.size_gb - a.size_gb);
                
                render(filtered);
            }
            
            render(models);
        </script>
    </body>
    </html>
    """
    return render_template_string(template, total_models=total_models, total_size=total_size, total_pulls=total_pulls, models_json=json.dumps(models))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
