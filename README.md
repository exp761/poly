# 🧠 PolyGenius — Prediction Market Research Bot

Ultra-powerful AI research assistant for Polymarket.
Analyzes markets from 5+ data sources and calculates calibrated probability estimates.

---

## 🎯 How It Works

```
Polymarket API    ──┐
Metaculus          ──┤
GDELT News         ──┼──► AI Analysis (Claude) ──► Probability Engine ──► Telegram Alert
Wikipedia          ──┤
Price History      ──┘
```

### Probability Calculation Weights
| Source | Weight |
|--------|--------|
| AI Analysis (Claude) | 35% |
| Historical Base Rate | 25% |
| Metaculus Expert Prediction | 20% |
| News Sentiment | 10% |
| Market Momentum | 10% |

---

## 🚀 Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
nano .env
```

Fill in:
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — from @userinfobot
- `OPENROUTER_API_KEY` — from openrouter.ai

### 3. Run
```bash
python main.py
```

### 4. Run as background service (VPS)
```bash
# Using tmux
tmux new -s polygenius
python main.py
# Ctrl+B then D to detach

# Using screen
screen -S polygenius
python main.py
# Ctrl+A then D to detach
```

---

## 📱 Telegram Commands

| Command | Description |
|---------|-------------|
| `/scan` | Scan all active markets for opportunities |
| `/top` | Top 5 best opportunities right now |
| `/analyze [keyword]` | Analyze markets matching keyword |
| `/market [id]` | Full analysis of one specific market |
| `/stats` | Bot statistics & track record |
| `/settings` | View current settings |
| Ask anything! | Natural language questions supported |

### Natural Language Examples
- "Berapa peluang Trump menang pilpres?"
- "Market crypto mana yang paling menarik minggu ini?"
- "Analisis semua market tentang AI"
- "Mana yang lebih bagus, bet YES atau NO di market Bitcoin?"

---

## 📊 Output Format

```
🔥 #1 Will Bitcoin reach $100k by end of 2025?
━━━━━━━━━━━━━━━━━━━━
📊 Market price: 42.0%
🧠 AI estimate: 61.0%
⚡ Edge: +19.0%
🎯 Bet: YES
💪 Confidence: High ✅
📝 Strong institutional buying + ETF inflows
```

---

## ⚙️ Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_EDGE_PCT` | `8` | Minimum edge % to trigger alert |
| `SCAN_INTERVAL_MIN` | `30` | Auto-scan interval (minutes) |
| `LLM_MODEL` | `anthropic/claude-sonnet-4-5` | AI model to use |

---

## ⚠️ Disclaimer

This bot is for **research purposes only**. 
Probability estimates are AI-generated and not financial advice.
Always do your own research before betting.
Past performance does not guarantee future results.
