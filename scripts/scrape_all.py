#!/usr/bin/env python3
"""
Comprehensive Ollama model scraper.
Extracts: name, description, owner, pulls, tags, updated date,
capabilities (vision/tools/thinking/audio/cloud/embedding),
sizes (parameter variants), context window, input types,
cloud usage level (1-4 pills), and download size per variant.
"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "ollama_rich_models.json"

# ─── Owner mapping (models without explicit namespace) ───
OWNER_MAP = {
    "llama3.1": "Meta", "llama3.2": "Meta", "llama3": "Meta", "llama3.2-vision": "Meta",
    "llama3.3": "Meta", "llama2": "Meta", "llama4": "Meta", "codellama": "Meta",
    "gemma4": "Google DeepMind", "gemma3": "Google DeepMind", "gemma2": "Google DeepMind",
    "gemma": "Google DeepMind", "codegemma": "Google DeepMind",
    "qwen3.5": "Alibaba Cloud", "qwen3.6": "Alibaba Cloud", "qwen3": "Alibaba Cloud",
    "qwen2.5": "Alibaba Cloud", "qwen2.5-coder": "Alibaba Cloud", "qwen2": "Alibaba Cloud",
    "qwen": "Alibaba Cloud", "qwq": "Alibaba Cloud", "qwen3-coder": "Alibaba Cloud",
    "qwen3-vl": "Alibaba Cloud",
    "deepseek-r1": "DeepSeek", "deepseek-v3": "DeepSeek", "deepseek-v2": "DeepSeek",
    "deepseek-coder": "DeepSeek", "deepseek-coder-v2": "DeepSeek",
    "deepseek-v4-flash": "DeepSeek", "deepseek-v4-pro": "DeepSeek",
    "mistral": "Mistral AI", "mistral-small3.2": "Mistral AI", "mistral-nemo": "Mistral AI",
    "mistral-medium-3.5": "Mistral AI", "mixtral": "Mistral AI", "mistral-large-3": "Mistral AI",
    "phi3": "Microsoft", "phi4": "Microsoft",
    "nomic-embed-text": "Nomic AI", "mxbai-embed-large": "Mixedbread AI",
    "llava": "LMMS Lab", "minicpm-v": "MiniCPM",
    "dolphin3": "Eric Hartford", "dolphin-llama3": "Eric Hartford",
    "granite3.1-moe": "IBM", "granite4": "IBM", "granite4.1": "IBM",
    "smollm2": "HuggingFace", "falcon3": "TII", "command-r": "Cohere",
    "cogito": "DeepCogito", "olmo2": "Allen AI",
    "starcoder2": "BigCode", "bge-m3": "BAAI", "snowflake-arctic-embed": "Snowflake",
    "tinyllama": "Meta",
    "glm-ocr": "Zhipu AI", "glm-5.1": "Zhipu AI", "glm-5.2": "Zhipu AI",
    "minimax-m2.7": "MiniMax", "minimax-m2.5": "MiniMax", "minimax-m3": "MiniMax",
    "nemotron-3-super": "NVIDIA", "nemotron3": "NVIDIA", "nemotron-3-ultra": "NVIDIA",
    "kimi-k2.7-code": "Moonshot AI", "kimi-k2.6": "Moonshot AI", "kimi-k2.5": "Moonshot AI",
    "gpt-oss": "OpenAI", "lfm2": "Liquid AI", "ornith": "Ornith",
    "laguna-xs-2.1": "Laguna",
}

# ─── Cloud usage level mapping ───
# From the Ollama pricing page: level 1 (lightest) to level 4 (heaviest)
CLOUD_USAGE_MAP = {
    # Level 1 - Light (small models, cheap to run)
    "gpt-oss:20b": 1, "gemma4:cloud": 1,
    # Level 2 - Medium
    "qwen3.5:cloud": 2, "qwen3.5:397b-cloud": 2,
    "minimax-m2.7": 2, "minimax-m2.5": 2,
    # Level 3 - High
    "glm-5.1:cloud": 3, "glm-5.2:cloud": 3,
    "minimax-m3": 3, "kimi-k2.7-code": 3, "kimi-k2.6": 3,
    "mistral-medium-3.5": 3, "mistral-large-3": 3,
    "gemma4:31b-cloud": 3,
    # Level 4 - Extra High (biggest, most expensive)
    "deepseek-v4-pro:cloud": 4, "deepseek-v4-flash:cloud": 4,
    "nemotron-3-ultra": 4,
}

def parse_pulls(text: str) -> int:
    """Convert '117.5M', '90.2M', '6.2M', '275.7K' to int."""
    text = text.strip().replace(",", "")
    m = re.match(r'([\d.]+)\s*(M|K|B)?', text, re.IGNORECASE)
    if not m:
        return 0
    num = float(m.group(1))
    unit = (m.group(2) or "").upper()
    if unit == "B":
        return int(num * 1_000_000_000)
    elif unit == "M":
        return int(num * 1_000_000)
    elif unit == "K":
        return int(num * 1_000)
    return int(num)


def scrape_library(session: requests.Session) -> list[dict]:
    """Scrape the Ollama library page for all model cards."""
    print("🔍 Scraping Ollama library page...")
    resp = session.get("https://ollama.com/library", timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    models = []
    for li in soup.select("li a[href^='/library/']"):
        # Extract structured data from each model card
        href = li.get("href", "")
        name = href.replace("/library/", "")
        if not name or name in ("", "search"):
            continue

        # Get description from the paragraph inside
        desc_el = li.find("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        # Get all the text content to parse out pulls, tags, updated
        full_text = li.get_text(" ", strip=True)

        # Extract capabilities and size tags from the visible tags
        tag_spans = li.find_all("span", class_=lambda c: c and "tag" in c.lower())
        # Also look for inline text that looks like tags
        all_text_parts = full_text.split()

        # Parse structured data from text
        pulls_val = 0
        tags_val = 0
        updated_val = ""
        capabilities = []
        sizes = []

        # Find pulls number
        pulls_match = re.search(r'([\d.]+[KMB]?)\s*Pulls', full_text)
        if pulls_match:
            pulls_val = parse_pulls(pulls_match.group(1))

        # Find tags count
        tags_match = re.search(r'(\d+)\s*Tags', full_text)
        if tags_match:
            tags_val = int(tags_match.group(1))

        # Find updated time
        updated_match = re.search(r'Updated\s+(.+?)(?:\s*$|\s*View)', full_text)
        if updated_match:
            updated_val = updated_match.group(1).strip().rstrip("View")

        # Determine capabilities from known badges
        # We'll also check the full text for capability keywords
        cap_keywords = ["vision", "tools", "thinking", "audio", "cloud", "embedding"]
        for cap in cap_keywords:
            if cap in full_text.lower():
                # Make sure it's a capability tag, not just in description
                # Check if it appears as a standalone badge before the pulls section
                if re.search(rf'\b{cap}\b', full_text, re.IGNORECASE):
                    capabilities.append(cap)

        # Extract size variants (like 8b, 70b, 405b, etc.)
        # These appear as small badges before the pulls count
        size_pattern = re.findall(r'\b(\d+(?:\.\d+)?[kmgb]+)\b', full_text, re.IGNORECASE)
        for s in size_pattern:
            s_lower = s.lower()
            if s_lower.endswith(('b', 'm', 'k', 'g')):
                # Check if it's a parameter size (not a metric like "M" for millions)
                # Parameter sizes are like 8b, 70b, 405b, 0.5b, 1.5b
                # Skip if it's clearly a metric (like 117.5M pulls)
                if not re.match(r'[\d.]+[MG]$', s, re.IGNORECASE):
                    sizes.append(s_lower)

        owner = OWNER_MAP.get(name, "")
        if not owner:
            # Try to derive from name patterns
            if "deepseek" in name.lower():
                owner = "DeepSeek"
            elif "qwen" in name.lower():
                owner = "Alibaba Cloud"
            elif "llama" in name.lower():
                owner = "Meta"
            elif "gemma" in name.lower():
                owner = "Google DeepMind"
            elif "mistral" in name.lower():
                owner = "Mistral AI"
            elif "phi" in name.lower():
                owner = "Microsoft"
            else:
                owner = name.split("-")[0].split("_")[0].title()

        models.append({
            "name": name,
            "description": desc,
            "owner": owner,
            "pulls": pulls_val,
            "tagsCount": tags_val,
            "updated": updated_val,
            "capabilities": capabilities,
            "sizes": sizes,
        })

    print(f"  Found {len(models)} models from library page")
    return models


def scrape_model_tags(session: requests.Session, model_name: str) -> dict:
    """Scrape a model's /tags page for deep metadata: context, input types, sizes, cloud usage."""
    url = f"https://ollama.com/library/{model_name}/tags"
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  ⚠ Error fetching {model_name}: {e}")
        return {}

    result = {
        "context_windows": [],   # e.g. ["128K", "256K"]
        "input_types": [],      # e.g. ["Text", "Image"]
        "tag_sizes": {},         # e.g. {"12b": "7.6GB", "26b": "18GB"}
        "cloud_usage_level": 0,  # 1-4 pills
        "cloud_context": "",     # e.g. "1M" for deepseek-v4-pro
    }

    text = soup.get_text(" ", strip=True)

    # Extract context windows (e.g., "128K context", "256K context window", "1M context window")
    ctx_matches = re.findall(r'(\d+[KMG]?)\s*context', text, re.IGNORECASE)
    result["context_windows"] = list(set(ctx_matches))

    # Extract input types (Text, Image, Audio)
    input_types = []
    if re.search(r'\bText\b', text):
        input_types.append("Text")
    if re.search(r'\bImage\b', text):
        input_types.append("Image")
    if re.search(r'\bAudio\b', text):
        input_types.append("Audio")
    result["input_types"] = input_types

    # Extract cloud usage level from the tags page
    # Format: "Low Usage", "Medium Usage", "High Usage", "Extra High Usage"
    if "Extra High Usage" in text:
        result["cloud_usage_level"] = 4
    elif "High Usage" in text:
        result["cloud_usage_level"] = 3
    elif "Medium Usage" in text:
        result["cloud_usage_level"] = 2
    elif "Low Usage" in text:
        result["cloud_usage_level"] = 1

    # Extract size info for each tag variant
    # Look for patterns like "7.6GB" associated with model tags
    # Parse the tag table rows
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 2:
            tag_name = cells[0].get_text(strip=True)
            size_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            # Extract size in GB
            size_match = re.search(r'([\d.]+)\s*GB', size_text)
            if size_match:
                result["tag_sizes"][tag_name] = size_text

    return result


def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })

    # ─── Step 1: Scrape library page for all models ───
    models = scrape_library(session)
    if not models:
        print("❌ No models found from library page. Falling back to existing data.")
        if OUTPUT.exists():
            print(f"  Using existing {OUTPUT}")
            return
        print("❌ No existing data either. Exiting.")
        return

    # ─── Step 2: Enrich each model with tag-page data ───
    print(f"\n🔍 Enriching {len(models)} models with tag-page data...")
    for i, model in enumerate(models):
        name = model["name"]
        print(f"  [{i+1}/{len(models)}] {name}...", end="", flush=True)
        tag_data = scrape_model_tags(session, name)

        if tag_data:
            # Merge context windows
            if tag_data.get("context_windows"):
                model["contextWindows"] = tag_data["context_windows"]
            else:
                model["contextWindows"] = []

            # Merge input types
            if tag_data.get("input_types"):
                model["inputTypes"] = tag_data["input_types"]
            else:
                model["inputTypes"] = []

            # Merge download sizes per variant
            if tag_data.get("tag_sizes"):
                model["downloadSizes"] = tag_data["tag_sizes"]
            else:
                model["downloadSizes"] = {}

            # Cloud usage level
            if tag_data.get("cloud_usage_level"):
                model["cloudUsageLevel"] = tag_data["cloud_usage_level"]
                # Also extract cloud context if present
                cloud_ctx = tag_data.get("cloud_context", "")
                if cloud_ctx:
                    model["cloudContext"] = cloud_ctx
            elif "cloud" in model.get("capabilities", []):
                model["cloudUsageLevel"] = CLOUD_USAGE_MAP.get(name, 2)  # default medium
            else:
                model["cloudUsageLevel"] = 0

            # Update capabilities from tag page if more specific
            # The tag page shows exact capabilities as badges
            # Check the page text for capability badges
            tag_caps = []
            tag_text = ""
            try:
                resp = session.get(f"https://ollama.com/library/{name}/tags", timeout=30)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Look for capability badges in the page
                    for badge in soup.find_all(string=re.compile(r'(vision|tools|thinking|audio|cloud|embedding)', re.I)):
                        parent = badge.parent
                        if parent:
                            cap = badge.strip().lower()
                            if cap in ["vision", "tools", "thinking", "audio", "cloud", "embedding"]:
                                tag_caps.append(cap)
            except:
                pass

            if tag_caps and len(tag_caps) > len(model.get("capabilities", [])):
                model["capabilities"] = list(set(tag_caps))

        time.sleep(0.5)  # Rate limit
        print(" ✓")

    # ─── Step 3: Save enriched data ───
    # Sort by pulls descending
    models.sort(key=lambda m: m.get("pulls", 0), reverse=True)

    # Add display-friendly pulls string
    for m in models:
        p = m.get("pulls", 0)
        if p >= 1_000_000:
            m["pullsDisplay"] = f"{p/1_000_000:.1f}M"
        elif p >= 1_000:
            m["pullsDisplay"] = f"{p/1_000:.1f}K"
        else:
            m["pullsDisplay"] = str(p)

    with open(OUTPUT, "w") as f:
        json.dump(models, f, indent=2)

    print(f"\n✅ Saved {len(models)} enriched models to {OUTPUT}")
    print(f"   Cloud models: {sum(1 for m in models if 'cloud' in m.get('capabilities', []))}")
    print(f"   Vision models: {sum(1 for m in models if 'vision' in m.get('capabilities', []))}")
    print(f"   Tools models: {sum(1 for m in models if 'tools' in m.get('capabilities', []))}")


if __name__ == "__main__":
    main()