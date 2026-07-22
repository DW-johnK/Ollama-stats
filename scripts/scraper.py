#!/usr/bin/env python3
"""Open Ollama - Model comparison dashboard scraper. Extracts models sorted by owner with size/capability filters."""

import subprocess
import json

def fetch_model_from_ollama_api(model_name):
    """Fetch detailed metadata about a single model from Ollama API."""
    url = f"https://ollama.com/api/tags/{model_name}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-H", "User-Agent: Mozilla/5.0", "-o", "-", "-O", "/dev/stdin", f"{url}?debug=true"],
            capture_output=True,
            timeout=30
        )
        output = json.loads(result.stdout) if result.stdout else False
        return extract_model_info(output, model_name.split(':')[0] if ':' in str(output).split('@')[-1][:8]) if output and len(output) > 2 else {'name': model_name.split('@')[-1], 'size': output.get('size', 'N/A')}
    except:
        return fetch_model_via_browser(model_name)

def fetch_all_popular_models():
    """Fetch popular models using curl based API calls with pagination simulation."""
    # From the browser snapshot, we can identify these top models on page 1 (sorted by Popular):
    popular_models = [
        "ornith",
        "laguna-xs-2.1",
        "gemma4",
        "qwen3.5",
        "qwen3.6",
        "glm-ocr",
        "glm-5.1",
        "minimax-m2.7",
        "llama3.1",
        "deepseek-r1",
        "nomic-embed-text",
        "llama3.2",
        "gemma3",
        "llama3",
        "codellama",  # Common one we expect to find on later pages too
    ]
    
    all_data = []
    for i, model_name in enumerate(popular_models):
        url = f"https://ollama.com/api/tags/{model_name}"
        try:
            result = subprocess.run(
                ["curl", "-s", f"{url}", "--user-agent", "Mozilla/5.0"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.stdout.strip():
                data = json.loads(result.stdout)
                if 'models' in data and len(data['models']) > 0:
                    models_info = []
                    for model in data['models']:
                        all_data.append({
                            "name": model.get('model', model_name),
                            "pullCount": model.get('size'),
                            "digest": model.get('digest')
                        })
        except Exception as e:
            print(f"Failed to fetch {model_name}: {e}")
    
    return all_data

if __name__ == "__main__":
    models = fetch_all_popular_models()
    # Save results for dashboard
