# Trump Tweet Analyzer

**ECE 110 Project - Data Analysis & Pattern Recognition**

A Python-based system that monitors and analyzes social media posts from public figures to identify posting patterns and correlations with market data.

## What It Does

- **Fetches posts** from X (Twitter) and Truth Social
- **Analyzes patterns** in posting behavior (timing, content, frequency)
- **Tracks correlations** between posts and S&P 500 market movements
- **Tests predictions** using historical data

## Core Features

1. **Real-time Monitoring** - Checks for new posts every 5 minutes
2. **Pattern Analysis** - Identifies posting time patterns, keyword usage, entity mentions
3. **Market Correlation** - Compares posting behavior with stock market data
4. **Simple Backtesting** - Tests prediction accuracy on historical data

## Project Structure

```
├── trump_monitor.py           # Main post monitoring script
├── utils.py                   # Helper functions
├── server.py                  # Web dashboard server
├── dashboard.html             # Interactive web dashboard
├── analysis_01_caps.py        # Analyzes CAPS usage patterns
├── analysis_02_timing.py      # Posting time analysis
├── analysis_04_entities.py    # Entity mention analysis (Iran, China, etc.)
├── analysis_06_market.py      # Market correlation analysis
├── analysis_08_backtest.py    # Simple backtesting
├── trump_code_cli.py          # Command line interface
└── data/                      # Data files
```

## Quick Start

### Option 1: Web Dashboard (Recommended)
```bash
# Start the web dashboard
python server.py

# Open your browser to:
# http://localhost:8888
```

### Option 2: Run Analysis Scripts
```bash
# Install dependencies
pip install -r requirements.txt

# Run entity analysis (shows Iran, China mentions, etc.)
python analysis_04_entities.py

# Run market correlation
python analysis_06_market.py

# Run CAPS pattern analysis
python analysis_01_caps.py
```

### Option 3: Real-time Monitoring
```bash
# Start real-time monitoring (checks every 1 minute)
python trump_monitor.py

# Check status
python trump_monitor.py --status
```

### Option 4: Use CLI
```bash
python trump_code_cli.py --help
python trump_code_cli.py signals
```

## Educational Purpose

This project demonstrates:
- **API integration** - Fetching data from multiple sources
- **Data processing** - Cleaning and organizing large datasets
- **Pattern recognition** - Finding correlations in time-series data
- **Statistical analysis** - Testing hypotheses with real data
- **Real-time systems** - Building monitoring loops

## Data Sources

- Truth Social public posts
- X (Twitter) public posts
- S&P 500 market data (via public APIs)

## Important Notes

⚠️ **FOR EDUCATIONAL PURPOSES ONLY**

This is a data analysis project demonstrating:
- Python programming concepts
- Data fetching and processing
- Statistical correlation analysis
- Real-time monitoring systems

**NOT for:**
- Financial advice or trading decisions
- Any commercial use
- Predictive accuracy claims



