#!/usr/bin/env python3
import json

with open('ollama_rich_models.json') as f:
    models = json.load(f)

compact = json.dumps([{
    'n': m['name'],
    'd': m.get('description', ''),
    'p': m.get('pulls', 0),
    'pd': m.get('pullsDisplay', ''),
    'tc': m.get('tagsCount', 0),
    'c': m.get('capabilities', []),
    's': m.get('sizes', []),
    'u': m.get('updated', '')
} for m in models])

with open('index.html') as f:
    html = f.read()

html = html.replace('PLACEHOLDER_MODELS', compact)

with open('index.html', 'w') as f:
    f.write(html)

print(f'Injected {len(models)} models. HTML size: {len(html)} bytes')