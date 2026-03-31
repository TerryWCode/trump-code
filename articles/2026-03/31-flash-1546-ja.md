這則推文的原文內容是空的 — 兩個 `---` 之間沒有任何文字。信心度 0% 也印證了這點。

沒有原文就無法引用關鍵句，寫出來的速報會是捏造的。

**可能原因：**
- RSS 抓到的是刪除/編輯後的空貼文
- 圖片/影片貼文沒有附文字，parser 只抓到空白
- Truth Social API 回傳了 metadata 但沒有 body

要我跳過這則，還是你有原文可以貼給我？

---
**📋 出典・分析手法**
- 原文：Truth Social
- リンク：https://truthsocial.com/@realDonaldTrump/116324560241476454
- 投稿日時：Tue, 31 Mar 2026 15:45:27 +0000
- 分析エンジン：Trump Code AI（Claude Opus / Gemini Flash）
- シグナル検出：7,400件以上の投稿から検証済み551ルール（z=5.39）
- 手法：NLPキーワード分類 → LLM因果推論 → 信頼度スコアリング
- データセット：trumpcode.washinmura.jp/api/data
- オープンソース：github.com/sstklen/trump-code
