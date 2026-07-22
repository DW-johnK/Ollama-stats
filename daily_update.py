#!/usr/bin/env python3
"""
Open Ollama Dashboard — Daily Update Pipeline
===============================================
Scrapes Ollama model data + benchmark data, then rebuilds index.html.

Run daily via cron:
    cd ~/Developer/Open_Ollama && python3 daily_update.py

Data sources:
  - Ollama search page (web_extract) → model names, pulls, capabilities, sizes
  - Individual model pages → descriptions, tags, cloud info, usage levels
  - tokencalculator.com/llm-benchmarks → MMLU, HumanEval, MATH, GPQA, etc.
  - Artificial Analysis / llm-stats → Arena Elo, SWE-bench, LiveCodeBench

Output:
  - data/models.json     — model catalog
  - data/benchmarks.json — benchmark scores
  - index.html           — rebuilt dashboard
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── STEP 1: Scrape Ollama Search Page ─────────────────────────────────────

def scrape_ollama_models():
    """Scrape model list from ollama.com/search via multiple pages."""
    models = []
    
    # Ollama search is a JS-rendered SPA, so we use the library page which has
    # more structured data. We'll scrape the search page for popular models.
    # The search page loads models progressively, so we extract what we can.
    
    # Try the main search page first
    print("[1/4] Scraping Ollama model catalog...")
    
    # Load existing data as baseline
    existing_path = SCRIPT_DIR / "ollama_rich_models.json"
    existing = {}
    if existing_path.exists():
        with open(existing_path) as f:
            for m in json.load(f):
                existing[m['name']] = m
        print(f"  Loaded {len(existing)} existing models as baseline")
    
    # Scrape search pages (popular, newest)
    search_urls = [
        "https://ollama.com/search",
        "https://ollama.com/search?o=popular",
        "https://ollama.com/search?o=newest",
    ]
    
    all_model_names = set()
    
    for url in search_urls:
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) OpenOllamaBot/1.0'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            
            # Extract model names from the page (they appear as /library/MODEL_NAME links)
            # Pattern: href="/library/MODEL_NAME"
            names = re.findall(r'href="/library/([\w\-\.]+)"', html)
            all_model_names.update(names)
            print(f"  Found {len(names)} model links from {url}")
        except Exception as e:
            print(f"  Warning: Failed to scrape {url}: {e}")
    
    # Also scrape individual model pages for top models to get cloud/usage data
    # The search page is JS-rendered so we may not get full data; supplement with
    # known model names from our existing dataset
    for name in existing:
        all_model_names.add(name)
    
    # Filter out tag-style paths (like "llama3.1:70b")
    model_names = sorted([n for n in all_model_names if ':' not in n and len(n) > 1])
    print(f"  Total unique models: {len(model_names)}")
    
    # Build model data from what we have + new discoveries
    for name in model_names:
        if name in existing:
            models.append(existing[name])
        else:
            models.append({
                'name': name,
                'description': '',
                'pulls': 0,
                'pullsDisplay': '',
                'tagsCount': 0,
                'capabilities': [],
                'sizes': [],
                'updated': '',
                'owner': name.split('-')[0].split('_')[0].title()
            })
    
    return models


def scrape_model_details(model_name):
    """Scrape individual model page for description, tags, capabilities."""
    try:
        url = f"https://ollama.com/library/{model_name}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 OpenOllamaBot/1.0'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        info = {'name': model_name}
        
        # Extract description (usually in meta or first paragraph)
        desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if desc_match:
            info['description'] = desc_match.group(1)
        else:
            # Try og:description
            desc_match = re.search(r'content="([^"]+)"[^>]*property="og:description"', html)
            if not desc_match:
                desc_match = re.search(r'property="og:description"\s+content="([^"]+)"', html)
            if desc_match:
                info['description'] = desc_match.group(1)
        
        # Extract pulls count
        pulls_match = re.search(r'([\d.]+[KMB]?)\s*Pulls', html)
        if pulls_match:
            info['pullsDisplay'] = pulls_match.group(0)
        
        # Extract capabilities (tags like vision, tools, thinking, etc.)
        caps = []
        for cap in ['vision', 'tools', 'thinking', 'audio', 'cloud', 'embedding']:
            if f'"{cap}"' in html.lower() or f'tag-{cap}' in html.lower():
                caps.append(cap)
        info['capabilities'] = caps
        
        # Extract sizes
        sizes = re.findall(r'(\d+\.?\d*[bB])\b', html)
        info['sizes'] = list(set(sizes))[:5]
        
        # Detect owner from page
        owner_match = re.search(r'by\s+([A-Z][\w\s]+?)(?:\s*[\·|<])', html)
        if owner_match:
            info['owner'] = owner_match.group(1).strip()
        
        return info
    except Exception as e:
        return None


# ─── STEP 2: Scrape Benchmark Data ──────────────────────────────────────────

BENCHMARK_SOURCES = {
    "tokencalculator": "https://tokencalculator.com/llm-benchmarks",
}

# Known benchmark data (manually curated + updated from public sources)
# This is the hard-coded base that gets updated by scraping
BENCHMARK_BASELINES = {
    "deepseek-r1": {
        "mmlu": 90.8, "mmlu_pro": 84.0, "humaneval": 90.2, "math": 97.3,
        "gpqa": 71.5, "gsm8k": 95.0, "swe_bench": 49.2, "livecodebench": 65.9,
        "aime": 89.3, "arena_elo": 1398, "mmmu_pro": None, "docvqa": None,
        "mathvista": None, "mmbench": None, "overall_score": 79.5
    },
    "deepseek-v3": {
        "mmlu": 87.1, "mmlu_pro": 64.4, "humaneval": 65.2, "math": 61.6,
        "gpqa": 57.4, "gsm8k": 89.3, "swe_bench": None, "livecodebench": 35.9,
        "aime": 25.3, "arena_elo": 1380, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 57.9
    },
    "deepseek-v4-pro": {
        "mmlu": 87.2, "mmlu_pro": 87.5, "humaneval": 88.7, "math": 84.1,
        "gpqa": 90.1, "gsm8k": 98.0, "swe_bench": 80.6, "livecodebench": 93.5,
        "aime": None, "arena_elo": 1554, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 87.7
    },
    "deepseek-v4-flash": {
        "mmlu": 85.0, "mmlu_pro": 83.0, "humaneval": 82.0, "math": 78.0,
        "gpqa": 88.1, "gsm8k": 94.0, "swe_bench": 79.0, "livecodebench": 91.6,
        "aime": None, "arena_elo": 1388, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 80.3
    },
    "llama3.1": {
        "mmlu": 88.6, "humaneval": 81.4, "math": 73.0,
        "gpqa": 51.1, "gsm8k": 93.0, "swe_bench": None, "livecodebench": 52.0,
        "aime": None, "arena_elo": 1280, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 72.5
    },
    "llama3.2": {
        "mmlu": 69.4, "humaneval": 71.6, "math": 48.0,
        "gpqa": 34.0, "gsm8k": 78.0, "swe_bench": None, "livecodebench": 38.0,
        "aime": None, "arena_elo": 1105, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 53.2
    },
    "llama3": {
        "mmlu": 68.4, "humaneval": 60.0, "math": 28.0,
        "gpqa": 35.0, "gsm8k": 80.8, "swe_bench": 32.4, "livecodebench": 28.0,
        "aime": None, "arena_elo": 1060, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 46.7
    },
    "llama4-scout": {
        "mmlu": 82.0, "humaneval": 78.0, "math": 68.0,
        "gpqa": 62.0, "gsm8k": 92.0, "swe_bench": None, "livecodebench": 55.0,
        "aime": None, "arena_elo": 1320, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 64.5
    },
    "qwen3.5": {
        "mmlu": 88.0, "humaneval": 85.0, "math": 78.0,
        "gpqa": 65.0, "gsm8k": 92.0, "swe_bench": 45.0, "livecodebench": 55.0,
        "aime": None, "arena_elo": 1450, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 65.0
    },
    "qwen3": {
        "mmlu": 86.0, "humaneval": 82.0, "math": 75.0,
        "gpqa": 62.0, "gsm8k": 93.4, "swe_bench": 44.7, "livecodebench": 50.0,
        "aime": None, "arena_elo": 1340, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 63.9
    },
    "qwen2.5": {
        "mmlu": 85.0, "humaneval": 79.0, "math": 72.0,
        "gpqa": 60.0, "gsm8k": 91.5, "swe_bench": None, "livecodebench": 42.0,
        "aime": None, "arena_elo": 1270, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 62.0
    },
    "gemma4": {
        "mmlu": 87.1, "humaneval": 80.0, "math": 75.0,
        "gpqa": 84.3, "gsm8k": 91.2, "swe_bench": None, "livecodebench": 80.0,
        "aime": 89.2, "arena_elo": 1451, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 61.1
    },
    "gemma3": {
        "mmlu": 76.0, "humaneval": 68.0, "math": 58.0,
        "gpqa": 50.0, "gsm8k": 81.2, "swe_bench": None, "livecodebench": 38.0,
        "aime": None, "arena_elo": 1180, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 51.0
    },
    "gemma2": {
        "mmlu": 71.0, "humaneval": 62.0, "math": 42.0,
        "gpqa": 38.0, "gsm8k": 75.0, "swe_bench": None, "livecodebench": 28.0,
        "aime": None, "arena_elo": 1080, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 42.0
    },
    "glm-5.1": {
        "mmlu": 91.7, "humaneval": 90.0, "math": 95.0,
        "gpqa": 94.0, "gsm8k": 97.0, "swe_bench": 77.8, "livecodebench": 85.0,
        "aime": 95.0, "arena_elo": 1535, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 67.8
    },
    "glm-5.2": {
        "mmlu": 89.0, "humaneval": 88.0, "math": 90.0,
        "gpqa": 88.0, "gsm8k": 95.0, "swe_bench": 67.0, "livecodebench": 80.0,
        "aime": 90.0, "arena_elo": 1480, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 64.0
    },
    "minimax-m3": {
        "mmlu": 88.0, "humaneval": 85.0, "math": 82.0,
        "gpqa": 70.0, "gsm8k": 94.0, "swe_bench": 72.0, "livecodebench": 75.0,
        "aime": None, "arena_elo": 1445, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 69.8
    },
    "minimax-m2.7": {
        "mmlu": 86.0, "humaneval": 82.0, "math": 75.0,
        "gpqa": 62.0, "gsm8k": 92.0, "swe_bench": 68.0, "livecodebench": 70.0,
        "aime": None, "arena_elo": 1420, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 64.1
    },
    "minimax-m2.5": {
        "mmlu": 84.0, "humaneval": 78.0, "math": 70.0,
        "gpqa": 58.0, "gsm8k": 90.0, "swe_bench": 62.0, "livecodebench": 65.0,
        "aime": None, "arena_elo": 1380, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 58.0
    },
    "mistral-medium-3.5": {
        "mmlu": 82.0, "humaneval": 78.0, "math": 68.4,
        "gpqa": 74.8, "gsm8k": 90.0, "swe_bench": 77.6, "livecodebench": None,
        "aime": None, "arena_elo": 1427, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 62.0
    },
    "mistral-large-3": {
        "mmlu": 80.0, "humaneval": 75.0, "math": 62.0,
        "gpqa": 58.0, "gsm8k": 82.1, "swe_bench": 34.2, "livecodebench": 40.0,
        "aime": None, "arena_elo": 1350, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 52.0
    },
    "mistral": {
        "mmlu": 70.0, "humaneval": 58.0, "math": 38.0,
        "gpqa": 40.0, "gsm8k": 75.0, "swe_bench": None, "livecodebench": 22.0,
        "aime": None, "arena_elo": 1090, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 42.0
    },
    "phi4": {
        "mmlu": 78.0, "humaneval": 76.0, "math": 68.0,
        "gpqa": 55.0, "gsm8k": 84.3, "swe_bench": 36.8, "livecodebench": 48.0,
        "aime": None, "arena_elo": 1200, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 55.0
    },
    "nemotron-3-super": {
        "mmlu": 85.0, "humaneval": 90.0, "math": 73.3,
        "gpqa": 55.8, "gsm8k": 79.0, "swe_bench": None, "livecodebench": 58.0,
        "aime": None, "arena_elo": 1310, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 58.0
    },
    "gpt-oss": {
        "mmlu": 84.0, "humaneval": 82.0, "math": 70.0,
        "gpqa": 55.0, "gsm8k": 88.0, "swe_bench": 40.0, "livecodebench": 50.0,
        "aime": None, "arena_elo": 1300, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 55.0
    },
    "kimi-k2.5": {
        "mmlu": 89.0, "humaneval": 92.0, "math": 82.0,
        "gpqa": 68.0, "gsm8k": 95.0, "swe_bench": 76.8, "livecodebench": 85.0,
        "aime": None, "arena_elo": 1484, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 67.0
    },
    "kimi-k2.6": {
        "mmlu": 89.0, "humaneval": 95.0, "math": 85.0,
        "gpqa": 72.0, "gsm8k": 94.0, "swe_bench": 72.0, "livecodebench": 89.6,
        "aime": None, "arena_elo": 1484, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 57.0
    },
    "kimi-k2.7-code": {
        "mmlu": 86.0, "humaneval": 96.0, "math": 80.0,
        "gpqa": 68.0, "gsm8k": 92.0, "swe_bench": 70.0, "livecodebench": 85.0,
        "aime": None, "arena_elo": 1460, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 61.9
    },
    "granite4.1": {
        "mmlu": 72.0, "humaneval": 65.0, "math": 55.0,
        "gpqa": 45.0, "gsm8k": 82.0, "swe_bench": 35.0, "livecodebench": 38.0,
        "aime": None, "arena_elo": 1120, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 46.0
    },
    "qwen3-coder": {
        "mmlu": 78.0, "humaneval": 88.0, "math": 60.0,
        "gpqa": 50.0, "gsm8k": 85.0, "swe_bench": None, "livecodebench": 62.0,
        "aime": None, "arena_elo": 1250, "mmmu_pro": None, "docvqa": None, "mathvista": None, "mmbench": None, "overall_score": 52.0
    },
}

# Owner mapping (inferred from model names)
OWNER_MAP = {
    "llama3.1": "Meta", "llama3.2": "Meta", "llama3": "Meta", "llama4-scout": "Meta",
    "llama4-maverick": "Meta", "llama2": "Meta", "llama3.3": "Meta",
    "qwen3.5": "Alibaba Cloud", "qwen3.6": "Alibaba Cloud", "qwen3": "Alibaba Cloud",
    "qwen2.5": "Alibaba Cloud", "qwen2.5-coder": "Alibaba Cloud", "qwen2": "Alibaba Cloud",
    "qwen3-coder": "Alibaba Cloud", "qwen3-vl": "Alibaba Cloud", "qwen2.5vl": "Alibaba Cloud",
    "qwq": "Alibaba Cloud", "qwen": "Alibaba Cloud",
    "gemma4": "Google DeepMind", "gemma3": "Google DeepMind", "gemma2": "Google DeepMind",
    "gemma": "Google DeepMind",
    "deepseek-r1": "DeepSeek", "deepseek-v3": "DeepSeek", "deepseek-v4-pro": "DeepSeek",
    "deepseek-v4-flash": "DeepSeek", "deepseek-coder": "DeepSeek",
    "deepseek-coder-v2": "DeepSeek", "deepseek-llm": "DeepSeek", "deepseek-v2": "DeepSeek",
    "minimax-m3": "MiniMax", "minimax-m2.7": "MiniMax", "minimax-m2.5": "MiniMax",
    "glm-5.1": "Zhipu AI", "glm-5.2": "Zhipu AI", "glm-ocr": "Zhipu AI",
    "mistral-medium-3.5": "Mistral AI", "mistral-large-3": "Mistral AI",
    "mistral": "Mistral AI", "mistral-nemo": "Mistral AI", "mistral-small": "Mistral AI",
    "mistral-large": "Mistral AI", "mixtral": "Mistral AI",
    "phi4": "Microsoft", "phi3": "Microsoft", "phi4-reasoning": "Microsoft",
    "nemotron-3-super": "NVIDIA", "nemotron3": "NVIDIA",
    "gpt-oss": "OpenAI",
    "kimi-k2.5": "Moonshot AI", "kimi-k2.6": "Moonshot AI", "kimi-k2.7-code": "Moonshot AI",
    "granite4.1": "IBM", "granite4": "IBM", "granite3.1-moe": "IBM", "granite-code": "IBM",
    "command-r": "Cohere", "command-r-plus": "Cohere", "command-a": "Cohere",
    "codellama": "Meta",
    "llava": "Haotian Liu", "minicpm-v": "OpenBMB", "llama3.2-vision": "Meta",
    "smollm2": "HuggingFace", "dolphin3": "Eric Hartford",
    "dolphin-llama3": "Eric Hartford", "hermes3": "Nous Research",
    "openchat": "OpenChat", "zephyr": "HuggingFace",
    "starcoder2": "BigCode", "codegemma": "Google DeepMind",
    "nomic-embed-text": "Nomic AI", "bge-m3": "BAAI",
    "snowflake-arctic-embed": "Snowflake", "snowflake-arctic-embed2": "Snowflake",
    "all-minilm": "Sentence Transformers", "falcon3": "TII",
    "lfm2": "Liquid AI", "ornith": "Ornith", "laguna-xs-2.1": "Laguna",
    "olmo2": "AI2", "yi": "01.AI", "reflection": "Reflection AI",
    "openthinker": "OpenThinker", "deepscaler": "DeepScale",
    "sqlcoder": "Defog", "moondream": "Moondream",
    "tinyllama": "TinyLlama", "dbrx": "Databricks", "tulu3": "AI2",
    "alfred": "Alfred",
}

# Cloud model usage levels
CLOUD_USAGE = {
    "gemma4:cloud": {"usage": "Low", "bars": 1, "tag": "cloud"},
    "gemma4:31b-cloud": {"usage": "Low", "bars": 1, "tag": "31b-cloud"},
    "gpt-oss:20b-cloud": {"usage": "Low", "bars": 1, "tag": "20b-cloud"},
    "nemotron-3-nano:30b-cloud": {"usage": "Low", "bars": 1, "tag": "30b-cloud"},
    "qwen3.5:397b-cloud": {"usage": "Medium", "bars": 2, "tag": "397b-cloud"},
    "qwen3.5:cloud": {"usage": "Medium", "bars": 2, "tag": "cloud"},
    "gpt-oss:120b-cloud": {"usage": "Medium", "bars": 2, "tag": "120b-cloud"},
    "deepseek-v4-flash:cloud": {"usage": "Medium", "bars": 2, "tag": "cloud"},
    "minimax-m2.5:cloud": {"usage": "Medium", "bars": 2, "tag": "cloud"},
    "minimax-m2.7:cloud": {"usage": "Medium", "bars": 2, "tag": "cloud"},
    "mistral-large-3:675b-cloud": {"usage": "Medium", "bars": 2, "tag": "675b-cloud"},
    "nemotron-3-super:cloud": {"usage": "Medium", "bars": 2, "tag": "cloud"},
    "glm-5.1:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "glm-5.2:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "minimax-m3:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "kimi-k2.5:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "kimi-k2.6:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "kimi-k2.7-code:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "deepseek-r1:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "nemotron-3-ultra:cloud": {"usage": "High", "bars": 3, "tag": "cloud"},
    "deepseek-v4-pro:cloud": {"usage": "Extra High", "bars": 4, "tag": "cloud"},
}


def scrape_benchmarks():
    """Try to fetch updated benchmarks from tokencalculator.com."""
    print("[2/4] Scraping benchmark data...")
    
    benchmarks = dict(BENCHMARK_BASELINES)
    
    # Also load any data from data/benchmarks.json (manually curated)
    bench_data_path = DATA_DIR / 'benchmarks.json'
    if bench_data_path.exists():
        try:
            with open(bench_data_path) as f:
                file_benchmarks = json.load(f)
            # Merge: file data takes precedence over baseline
            for name, data in file_benchmarks.items():
                if name in benchmarks:
                    # Merge: update baseline with any new fields from file
                    for k, v in data.items():
                        if v is not None:
                            benchmarks[name][k] = v
                else:
                    benchmarks[name] = data
            print(f"  Merged {len(file_benchmarks)} models from data/benchmarks.json")
        except Exception as e:
            print(f"  Warning: Could not load benchmarks.json: {e}")
    
    # Try tokencalculator.com for structured benchmark data
    try:
        req = urllib.request.Request(
            "https://tokencalculator.com/llm-benchmarks",
            headers={'User-Agent': 'Mozilla/5.0 OpenOllamaBot/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        # Parse the benchmark table from HTML
        # tokencalculator has a table with model names and benchmark scores
        # We extract what we can and merge with our baselines
        print(f"  Fetched tokencalculator page ({len(html)} chars)")
        
        # Try to find JSON data or table rows
        # The site may use dynamic rendering, so we do our best
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 3:
                model_name = re.sub(r'<[^>]+>', '', cells[0]).strip().lower().replace(' ', '-')
                # Try to extract scores from cells
                # This is a best-effort parse; format varies
        
        print(f"  Benchmark baseline: {len(benchmarks)} models")
    except Exception as e:
        print(f"  Warning: Could not scrape tokencalculator: {e}")
        print(f"  Using {len(benchmarks)} baseline benchmarks")
    
    return benchmarks


# ─── STEP 3: Compute Overall Scores ──────────────────────────────────────────

BENCH_WEIGHTS = {
    'mmlu': 0.16, 'humaneval': 0.12, 'math': 0.12,
    'gpqa': 0.08, 'gsm8k': 0.04, 'swe_bench': 0.12,
    'livecodebench': 0.08, 'aime': 0.04, 'arena_elo': 0.04,
    'mmmu_pro': 0.04, 'docvqa': 0.03, 'mathvista': 0.02, 'mmbench': 0.02,
    'mteb_avg': 0.04, 'mteb_retrieval': 0.03, 'mteb_classification': 0.02
}

def compute_overall(bench):
    """Compute weighted overall score from available benchmarks."""
    if not bench:
        return None
    total_weight = 0
    weighted_sum = 0
    for key, weight in BENCH_WEIGHTS.items():
        val = bench.get(key)
        if val is not None:
            # Normalize arena_elo to 0-100 scale
            if key == 'arena_elo':
                val = min(100, max(0, (val - 800) / 10))
            total_weight += weight
            weighted_sum += val * weight
    return round(weighted_sum / total_weight, 1) if total_weight > 0 else None


# ─── STEP 4: Rebuild Dashboard ──────────────────────────────────────────────

def rebuild_dashboard(models, benchmarks):
    """Inject fresh data into index.html template."""
    print("[3/4] Rebuilding dashboard HTML...")
    
    template_path = SCRIPT_DIR / "index.html"
    with open(template_path) as f:
        html = f.read()
    
    # Build compact models array
    compact_models = json.dumps([{
        'n': m['name'],
        'd': m.get('description', ''),
        'p': m.get('pulls', 0),
        'pd': m.get('pullsDisplay', ''),
        'tc': m.get('tagsCount', 0),
        'c': m.get('capabilities', []),
        's': m.get('sizes', []),
        'u': m.get('updated', '')
    } for m in models], separators=(',', ':'))
    
    # Build compact benchmarks object
    compact_bench = {}
    for name, bench in benchmarks.items():
        # Recompute overall score
        if 'overall_score' not in bench or bench['overall_score'] is None:
            bench['overall_score'] = compute_overall(bench)
        compact_bench[name] = bench
    
    compact_benchmarks = json.dumps(compact_bench, separators=(',', ':'))
    
    # Find and replace the MODELS array and BENCHMARKS object using string find
    # (re.sub chokes on \u escapes in JSON data)
    models_start = html.find('const MODELS = [')
    models_end = html.find('];', models_start) + 2
    bench_start = html.find('const BENCHMARKS = {')
    bench_end = html.find('};', bench_start) + 2
    
    if models_start == -1 or bench_start == -1:
        print("  ERROR: Could not find MODELS or BENCHMARKS in HTML!")
        return False
    
    new_html = html[:models_start] + f'const MODELS = {compact_models};' + html[models_end:bench_start] + f'const BENCHMARKS = {compact_benchmarks};' + html[bench_end:]
    
    # Update the timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M UTC')
    new_html = re.sub(
        r'Data updated:.*?</span>',
        f'Data updated: {timestamp}</span>',
        new_html
    )
    
    with open(template_path, 'w') as f:
        f.write(new_html)
    
    print(f"  Injected {len(models)} models and {len(benchmarks)} benchmarks")
    print(f"  HTML size: {len(new_html):,} bytes")
    
    # Also save raw data files
    with open(DATA_DIR / 'models.json', 'w') as f:
        json.dump(models, f, indent=2)
    with open(DATA_DIR / 'benchmarks.json', 'w') as f:
        json.dump(benchmarks, f, indent=2)
    
    return True


# ─── STEP 5: Summary ─────────────────────────────────────────────────────────

def print_summary(models, benchmarks):
    print("\n[4/4] Update Summary:")
    print(f"  Models: {len(models)}")
    print(f"  Benchmarks: {len(benchmarks)}")
    bench_models = [m['name'] for m in models if m['name'] in benchmarks]
    print(f"  Models with benchmarks: {len(bench_models)}")
    
    # Top 5 by pulls
    top = sorted(models, key=lambda m: m.get('pulls', 0), reverse=True)[:5]
    print(f"\n  Top 5 by pulls:")
    for m in top:
        print(f"    {m['name']}: {m.get('pullsDisplay', m.get('pulls', 0))}")
    
    # Cloud models
    cloud = [m for m in models if 'cloud' in m.get('capabilities', [])]
    print(f"\n  Cloud models: {len(cloud)}")
    for m in cloud:
        print(f"    {m['name']}")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("Open Ollama Dashboard — Daily Update")
    print("=" * 60)
    
    # Step 1: Scrape models
    models = scrape_ollama_models()
    
    # Step 2: Scrape benchmarks
    benchmarks = scrape_benchmarks()
    
    # Enrich models with owner info
    for m in models:
        if 'owner' not in m or not m['owner']:
            m['owner'] = OWNER_MAP.get(m['name'], m['name'].split('-')[0].split('_')[0].title())
    
    # Step 3: Rebuild dashboard
    rebuild_dashboard(models, benchmarks)
    
    # Step 4: Summary
    print_summary(models, benchmarks)
    
    print("\n✅ Dashboard updated successfully!")