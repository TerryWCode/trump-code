# 交接文件
> 日期：2026-03-16 | 摘要：史詩級 session — 前端重寫 + i18n + Polymarket API + GitHub 大整理 + SEO/AEO + 跟單機器人研究

## 已完成

### 官網 (trumpcode.washinmura.jp)
- [x] 前端 insights.html 從零重寫 — 1,500+ 行
- [x] i18n 語言切換 EN/中/日 — 174 組三語，左上角按鈕，localStorage 記住
- [x] Polymarket 接上正確的 `/public-search` API — 315+ 個 Trump 市場即時顯示
- [x] 川普推文展示 — `/api/recent-posts` 最近 20 篇 + 信號分析
- [x] SEO 最高標準 — JSON-LD (WebApp + FAQ)、meta tags、canonical、OG locale
- [x] AEO 最高標準 — llms.txt、robots.txt（歡迎 AI 爬蟲）、sitemap.xml
- [x] 訪客統計 — `/api/analytics`（每日/每小時/UA 分類/頁面排行）
- [x] 聊天記錄 — `/api/chat-log`（保留 10,000 筆）
- [x] 兄弟網站互連 — Trump Code ↔ AEO Hub 頂部+底部雙向導流
- [x] Buy Me a Claude Max — 右上角 + Footer
- [x] Active Computation 搬到 Live Status 上面 + 掃描動畫
- [x] Cron 改每天都跑（原本只有週一到五）
- [x] 80 個獨立訪客（上線第一天）

### GitHub
- [x] README 重寫 — 純英文 + docs/README.zh.md + docs/README.ja.md
- [x] Repo 整理 — 31 → 15 個（刪 11 fork、合併 7+3+4、封存 16）
- [x] 9 個公開 repo 全部三語 README + 三語 description
- [x] Profile README 優化 — 故事感 + Usage 數據 + GitHub Stats + 三語
- [x] Discussions 開通 — 5 個討論帖
- [x] ⭐ 189 stars, 18 forks（第一天）
- [x] washin-playbook 新 repo（合併 7 個展示 repo）
- [x] washin-travel 新 repo（合併 4 個旅遊 repo）
- [x] ClawAPI 吸收 drclaw + internal，README 三語更新

### 推廣
- [x] X 推文三語文案 — EN/ZH/JA + @mentions + hashtags
- [x] 發文排程建議 — 日文中午12點/中文晚上7點/英文晚上10點（JST）
- [x] FB OG tags 修復（FB 仍擋新網域，建議用 GitHub 連結或短網址）

## 進行中
- [ ] 跟單 AI 機器人 — 已完成研究，建議做 $TRUMP 幣跟單（最簡單）
- [ ] 即時推文更新 — realtime_loop.py 偵測的新推文需寫回 trump_posts_all.json
- [ ] 根目錄 43 個 .py 檔案整理 — 決定暫不動（怕改 import 影響線上）

## 已知問題
- FB 封鎖新網域 — trumpcode.washinmura.jp 在 FB 分享會「找不到頁面」，需等 24-48h 或申訴
- Gamma API `slug_contains` 壞掉 — 已改用 `public-search`，但 polymarket_client.py 還是舊的
- BrokenPipeError — server log 有斷管錯誤（訪客斷開），不影響功能但應加 try/except
- og:image 還沒做 — 需要一張 OG 預覽圖（1200×630）

## 下一步（按優先順序）
1. 跟單機器人 — $TRUMP 幣信號→Binance API 自動下單
2. Telegram Bot — 信號即時推送給訂閱者
3. 即時推文 — 讓網站顯示最新的川普推文（不只到 3/14）
4. OG 預覽圖 — 做一張漂亮的 1200×630 社群分享圖
5. FB 申訴 — https://www.facebook.com/help/contact/571927962827151
6. Pin 6 個 repo — 手動去 GitHub 操作（trump-code/yes.md/infinite-gratitude/washin-playbook/5x-cto/ai-md）

## 重要連結
- 線上：https://trumpcode.washinmura.jp
- GitHub：https://github.com/sstklen/trump-code
- AEO Hub：https://aeo.washinmura.jp
- 訪客統計：https://trumpcode.washinmura.jp/api/analytics
- 聊天記錄：https://trumpcode.washinmura.jp/api/chat-log
- VPS：/home/ubuntu/trump-code/（python3 chatbot_server.py）
- Cron：每天 22:30 UTC 跑 daily_pipeline.py
