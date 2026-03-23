#!/usr/bin/env python3
"""生成 sitemap.xml 到 public/sitemap.xml"""

import json
import os
from datetime import date
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

BASE_URL = "https://trumpcode.washinmura.jp"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(PROJECT_DIR, "public")
INDEX_JSON = os.path.join(PROJECT_DIR, "articles", "index.json")
OUTPUT = os.path.join(PUBLIC_DIR, "sitemap.xml")

TODAY = date.today().isoformat()

XMLNS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# 要排除的檔案模式
EXCLUDE_PATTERNS = (".bak", "preview")


def load_article_dates() -> list[str]:
    with open(INDEX_JSON, "r") as f:
        return json.load(f)


def scan_html_files() -> list[str]:
    """掃描 public/ 下的 .html，排除 .bak 和 preview 檔案"""
    results = []
    for fname in sorted(os.listdir(PUBLIC_DIR)):
        if not fname.endswith(".html"):
            continue
        if any(pat in fname for pat in EXCLUDE_PATTERNS):
            continue
        results.append(fname)
    return results


def add_url(parent: Element, loc: str, lastmod: str, changefreq: str, priority: str):
    url_el = SubElement(parent, "url")
    SubElement(url_el, "loc").text = loc
    SubElement(url_el, "lastmod").text = lastmod
    SubElement(url_el, "changefreq").text = changefreq
    SubElement(url_el, "priority").text = priority


def generate():
    article_dates = load_article_dates()
    html_files = scan_html_files()

    urlset = Element("urlset", xmlns=XMLNS)

    # 1) 首頁
    add_url(urlset, f"{BASE_URL}/", TODAY, "daily", "1.0")

    # 2) HTML 頁面（排除首頁用的 index.html 若有）
    static_pages = {"daily.html", "game.html", "analysis.html", "achievement.html"}
    for fname in html_files:
        if fname in static_pages:
            add_url(urlset, f"{BASE_URL}/{fname}", TODAY, "daily", "0.8")

    # 其他非 static 的 HTML（如 insights.html），也加進去但給較低 priority
    for fname in html_files:
        if fname not in static_pages and fname != "index.html":
            add_url(urlset, f"{BASE_URL}/{fname}", TODAY, "weekly", "0.6")

    # 3) 每日文章頁面
    for d in article_dates:
        add_url(urlset, f"{BASE_URL}/daily.html?date={d}", d, "daily", "0.7")

    # 4) API 端點
    api_endpoints = [
        "/api/dashboard",
        "/api/signals",
        "/api/models",
        "/api/recent-posts",
    ]
    for ep in api_endpoints:
        add_url(urlset, f"{BASE_URL}{ep}", TODAY, "hourly", "0.6")

    # 5) llms.txt
    add_url(urlset, f"{BASE_URL}/llms.txt", TODAY, "weekly", "0.5")

    # 寫出
    indent(urlset, space="  ")
    tree = ElementTree(urlset)
    with open(OUTPUT, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="unicode" if False else "UTF-8", xml_declaration=False)

    # 統計
    url_count = len(urlset.findall("url"))
    print(f"Sitemap 已生成: {OUTPUT}")
    print(f"共 {url_count} 個 URL")
    print(f"  - 首頁: 1")
    print(f"  - HTML 頁面: {len([f for f in html_files if f in static_pages])}")
    print(f"  - 其他頁面: {len([f for f in html_files if f not in static_pages and f != 'index.html'])}")
    print(f"  - 每日文章: {len(article_dates)}")
    print(f"  - API 端點: {len(api_endpoints)}")
    print(f"  - llms.txt: 1")


if __name__ == "__main__":
    generate()
