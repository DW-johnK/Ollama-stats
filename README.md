# 🦙 Open Ollama — Model Explorer, Comparator & Benchmarks

An open-source dashboard for exploring, comparing, and benchmarking AI models available on [ollama.com](https://ollama.com). Browse 99+ models across 16 owners, compare benchmarks side-by-side, filter by capabilities, and sort by cost — all in a single self-contained HTML file.

**Live demo:** Serve locally with `python3 -m http.server 5000` and open [http://localhost:5000](http://localhost:5000).

![Light Theme](docs/screenshot-light.png) ![Dark Theme](docs/screenshot-dark.png)

---

## ✨ Features

- **99+ models** scraped from ollama.com with rich metadata (description, tags, sizes, pull counts)
- **46 models with benchmarks** — MMLU, HumanEval, MATH, GPQA, GSM8K, SWE-bench, LiveCodeBench, AIME, Arena Elo
- **Vision benchmarks** — MMMU-Pro, DocVQA, MathVista, MMBench for multimodal models
- **Embedding benchmarks** — MTEB Average, MTEB Retrieval, MTEB Classification
- **Overall Score** — weighted composite ranking across all benchmarks
- **Grouped by owner** — Meta, Alibaba, DeepSeek, Google, Mistral, Microsoft, etc.
- **Capability filters** — Vision, Tools, Thinking, Cloud, Audio, Embedding
- **Cost comparison** — Cloud pricing tiers ($/1M tokens) for hosted models
- **Dark & light themes** — toggle with 🌓/☀️ button, persists via localStorage
- **Daily auto-update** — cron job scrapes latest model data and benchmarks every morning
- **Compare mode** — select models and view them side-by-side in a detailed table
- **Zero dependencies** — single `index.html`, no build step, no npm

---

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/DW-johnK/Ollama-stats.git
cd Ollama-stats

# Serve locally
python3 -m http.server 5000

# Open in browser
open http://localhost:5000
```

That's it. No install, no build, no config.

---

## 📊 Benchmark Coverage

| Category | Models | Benchmarks |
|----------|--------|------------|
| Text LLMs | 30+ | MMLU, HumanEval, MATH, GPQA, GSM8K, SWE-bench, LiveCodeBench, AIME, Arena Elo |
| Vision/Multimodal | 7 | MMMU-Pro, DocVQA, MathVista, MMBench |
| Embedding | 6 | MTEB Average, MTEB Retrieval, MTEB Classification |

Benchmark sources: official model cards, HuggingFace leaderboards, tokencalculator.com, and published evaluation reports.

---

## 🔄 Daily Updates

The dashboard auto-updates via a daily cron job that:

1. Scrapes the latest model catalog from `ollama.com/search` (20+ pages)
2. Fetches benchmark scores from multiple sources
3. Merges manually curated data from `data/benchmarks.json`
4. Injects everything into `index.html`

```bash
# Run manually
python3 daily_update.py

# Or let the cron handle it (6:00 AM daily)
```

---

## 🎨 Themes

| Light Theme | Dark Theme |
|-------------|------------|
| White `#fff` background | Deep navy `#080c14` background |
| Red `#d40808` accents (Ollama brand) | Purple `#8b5cf6` accents |
| Pastel capability tags | Saturated capability tags |
| Clean, minimal | Developer-focused |

Toggle between themes with the 🌓/☀️ button in the header. Your preference is saved in localStorage.

---

## 📁 Project Structure

```
Ollama-stats/
├── index.html            # Self-contained dashboard (the main deliverable)
├── daily_update.py       # Scraper + data injection pipeline
├── data/
│   ├── benchmarks.json   # Manually curated benchmark scores (merged daily)
│   └── models.json       # Auto-generated model catalog
├── favicon-32.png        # Browser icon (32×32)
├── apple-touch-icon.png  # iOS home screen icon (180×180)
├── android-chrome-192x192.png  # Android icon
├── inject_data.py         # Data injection helper
├── save_rich_data.py      # Rich metadata scraper
├── build_dashboard.py     # Dashboard builder (predecessor)
├── app.py                 # Flask server (alternative to python -m http.server)
├── .gitignore
└── README.md
```

---

## 🛠 Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS — zero dependencies, single file
- **Data:** JSON embedded inline, auto-refreshed daily
- **Scraping:** Python + web_extract from ollama.com
- **Benchmarks:** Curated from official reports, HuggingFace, tokencalculator.com
- **Serving:** `python3 -m http.server` or Flask (`app.py`)

---

## 📜 License

MIT — use it, fork it, share it.

---

Built by [Collide](https://collide.io) — AI applications for oil & gas operations.