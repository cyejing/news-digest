#!/usr/bin/env python3
"""
Fetch news from web crawlers and API sources.

Supports:
- Hacker News (web scraper)
- V2EX (API)
- Weibo Hot Search (API)
- WallStreetCN (API)
- Tencent News (API)
- 36Kr (web scraper)

Usage:
    python3 fetch-crawler.py [--defaults DIR] [--config DIR] [--output FILE] [--verbose]
"""

import json
import re
import sys
import os
import argparse
import logging
import time
import tempfile
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

TIMEOUT = 15
MAX_WORKERS = 6
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"


class RedirectHandler308(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code in (301, 302, 303, 307, 308):
            newurl = newurl.replace(' ', '%20')
            new_headers = dict(req.headers)
            return Request(newurl, headers=new_headers, method=req.get_method())
        return None


def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def http_get(url: str, headers: Dict[str, str] = None, timeout: int = TIMEOUT) -> str:
    """HTTP GET with fallback between requests and urllib."""
    req_headers = {"User-Agent": UA}
    if headers:
        req_headers.update(headers)
    
    if HAS_REQUESTS:
        resp = requests.get(url, headers=req_headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    else:
        opener = build_opener(RedirectHandler308)
        req = Request(url, headers=req_headers)
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")


def http_get_json(url: str, headers: Dict[str, str] = None, timeout: int = TIMEOUT) -> Dict:
    """HTTP GET JSON response."""
    req_headers = {"User-Agent": UA}
    if headers:
        req_headers.update(headers)
    
    if HAS_REQUESTS:
        resp = requests.get(url, headers=req_headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    else:
        opener = build_opener(RedirectHandler308)
        req = Request(url, headers=req_headers)
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_hackernews(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch Hacker News frontpage via web scraping."""
    articles = []
    try:
        html = http_get("https://news.ycombinator.com")
        
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.select('.athing')
            
            for row in rows[:limit]:
                try:
                    id_ = row.get('id')
                    title_line = row.select_one('.titleline a')
                    if not title_line:
                        continue
                    title = title_line.get_text()
                    link = title_line.get('href')
                    
                    score_span = soup.select_one(f'#score_{id_}')
                    score = score_span.get_text() if score_span else "0 points"
                    
                    age_span = soup.select_one(f'.age a[href="item?id={id_}"]')
                    time_str = age_span.get_text() if age_span else ""
                    
                    if link and link.startswith('item?id='):
                        link = f"https://news.ycombinator.com/{link}"
                    
                    articles.append({
                        "title": title[:200],
                        "link": link,
                        "date": datetime.now(timezone.utc).isoformat(),
                        "source_id": "hackernews-crawler",
                        "source_type": "crawler",
                        "source_name": "Hacker News",
                        "topics": ["frontier-tech"],
                        "heat": score,
                        "time_ago": time_str,
                    })
                except Exception:
                    continue
        else:
            for item in re.finditer(r'<tr class="athing" id="(\d+)".*?<span class="titleline"><a href="([^"]+)">([^<]+)</a>', html, re.DOTALL):
                id_, link, title = item.groups()
                score_m = re.search(rf'id="score_{id_}">(\d+ points)', html)
                score = score_m.group(1) if score_m else "0 points"
                
                if link.startswith('item?id='):
                    link = f"https://news.ycombinator.com/{link}"
                
                articles.append({
                    "title": title[:200],
                    "link": link,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "source_id": "hackernews-crawler",
                    "source_type": "crawler",
                    "source_name": "Hacker News",
                    "topics": ["frontier-tech"],
                    "heat": score,
                })
                
                if len(articles) >= limit:
                    break
    except Exception as e:
        logging.debug(f"Hacker News fetch failed: {e}")
    
    return articles


def fetch_v2ex(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch V2EX hot topics via API."""
    articles = []
    try:
        data = http_get_json("https://www.v2ex.com/api/topics/hot.json")
        
        for t in data[:limit]:
            replies = t.get('replies', 0)
            articles.append({
                "title": t.get('title', '')[:200],
                "link": t.get('url', ''),
                "date": datetime.now(timezone.utc).isoformat(),
                "source_id": "v2ex-api",
                "source_type": "crawler",
                "source_name": "V2EX",
                "topics": ["frontier-tech"],
                "heat": f"{replies} replies",
            })
    except Exception as e:
        logging.debug(f"V2EX fetch failed: {e}")
    
    return articles


def fetch_weibo(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch Weibo hot search via API."""
    articles = []
    try:
        headers = {"Referer": "https://weibo.com/"}
        data = http_get_json("https://weibo.com/ajax/side/hotSearch", headers=headers)
        
        items = data.get('data', {}).get('realtime', [])
        
        for item in items[:limit]:
            title = item.get('note', '') or item.get('word', '')
            if not title:
                continue
            
            heat = item.get('num', 0)
            url = f"https://s.weibo.com/weibo?q={title}"
            
            articles.append({
                "title": title[:200],
                "link": url,
                "date": datetime.now(timezone.utc).isoformat(),
                "source_id": "weibo-api",
                "source_type": "crawler",
                "source_name": "Weibo Hot Search",
                "topics": ["news"],
                "heat": str(heat),
            })
    except Exception as e:
        logging.debug(f"Weibo fetch failed: {e}")
    
    return articles


def fetch_wallstreetcn(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch WallStreetCN news via API."""
    articles = []
    try:
        url = "https://api-one.wallstcn.com/apiv1/content/information-flow?channel=global-channel&accept=article&limit=30"
        data = http_get_json(url)
        
        for item in data.get('data', {}).get('items', [])[:limit]:
            res = item.get('resource')
            if res and (res.get('title') or res.get('content_short')):
                ts = res.get('display_time', 0)
                time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else ""
                
                articles.append({
                    "title": (res.get('title') or res.get('content_short', ''))[:200],
                    "link": res.get('uri', ''),
                    "date": time_str,
                    "source_id": "wallstreetcn-api",
                    "source_type": "crawler",
                    "source_name": "Wall Street CN",
                    "topics": ["news"],
                })
    except Exception as e:
        logging.debug(f"WallStreetCN fetch failed: {e}")
    
    return articles


def fetch_tencent(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch Tencent News via API."""
    articles = []
    try:
        headers = {"Referer": "https://news.qq.com/"}
        url = "https://i.news.qq.com/web_backend/v2/getTagInfo?tagId=aEWqxLtdgmQ%3D"
        data = http_get_json(url, headers=headers)
        
        for news in data.get('data', {}).get('tabs', [{}])[0].get('articleList', [])[:limit]:
            articles.append({
                "title": news.get('title', '')[:200],
                "link": news.get('url') or news.get('link_info', {}).get('url', ''),
                "date": news.get('pub_time', '') or news.get('publish_time', ''),
                "source_id": "tencent-api",
                "source_type": "crawler",
                "source_name": "Tencent News",
                "topics": ["news"],
            })
    except Exception as e:
        logging.debug(f"Tencent News fetch failed: {e}")
    
    return articles


def fetch_36kr(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch 36Kr newsflashes via web scraping."""
    articles = []
    try:
        html = http_get("https://36kr.com/newsflashes")
        
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            for item in soup.select('.newsflash-item')[:limit]:
                title_elem = item.select_one('.item-title')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                time_tag = item.select_one('.time')
                time_str = time_tag.get_text(strip=True) if time_tag else ""
                
                link = f"https://36kr.com{href}" if not href.startswith('http') else href
                
                articles.append({
                    "title": title[:200],
                    "link": link,
                    "date": time_str,
                    "source_id": "36kr-crawler",
                    "source_type": "crawler",
                    "source_name": "36Kr",
                    "topics": ["news"],
                })
        else:
            for item in re.finditer(r'<div class="newsflash-item".*?<a[^>]*href="([^"]*)"[^>]*class="item-title"[^>]*>([^<]+)</a>', html, re.DOTALL):
                href, title = item.groups()
                link = f"https://36kr.com{href}" if not href.startswith('http') else href
                
                articles.append({
                    "title": title.strip()[:200],
                    "link": link,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "source_id": "36kr-crawler",
                    "source_type": "crawler",
                    "source_name": "36Kr",
                    "topics": ["frontier-tech"],
                })
                
                if len(articles) >= limit:
                    break
    except Exception as e:
        logging.debug(f"36Kr fetch failed: {e}")
    
    return articles


def load_crawler_sources(defaults_dir: Path, config_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load crawler sources from unified configuration."""
    try:
        from config_loader import load_merged_sources
    except ImportError:
        import sys
        sys.path.append(str(Path(__file__).parent))
        from config_loader import load_merged_sources
    
    all_sources = load_merged_sources(defaults_dir, config_dir)
    
    crawler_sources = []
    for source in all_sources:
        if source.get("type") == "crawler" and source.get("enabled", True):
            crawler_sources.append(source)
    
    if not crawler_sources:
        crawler_sources = [
            {"id": "hackernews-crawler", "name": "Hacker News", "topics": ["news"], "priority": True},
            {"id": "v2ex-api", "name": "V2EX", "topics": ["news"], "priority": True},
            {"id": "weibo-api", "name": "Weibo Hot Search", "topics": ["news"], "priority": False},
            {"id": "wallstreetcn-api", "name": "Wall Street CN", "topics": ["news"], "priority": True},
            {"id": "tencent-api", "name": "Tencent News", "topics": ["news"], "priority": False},
            {"id": "36kr-crawler", "name": "36Kr", "topics": ["news"], "priority": True},
        ]
    
    logging.info(f"Loaded {len(crawler_sources)} crawler sources")
    return crawler_sources


def fetch_source(source: Dict[str, Any], limit: int = 15) -> Dict[str, Any]:
    """Fetch a single crawler source."""
    source_id = source["id"]
    name = source.get("name", source_id)
    topics = source.get("topics", [])
    priority = source.get("priority", False)
    
    fetchers = {
        "hackernews-crawler": fetch_hackernews,
        "v2ex-api": fetch_v2ex,
        "weibo-api": fetch_weibo,
        "wallstreetcn-api": fetch_wallstreetcn,
        "tencent-api": fetch_tencent,
        "36kr-crawler": fetch_36kr,
    }
    
    fetcher = fetchers.get(source_id)
    if not fetcher:
        return {
            "source_id": source_id,
            "source_type": "crawler",
            "name": name,
            "priority": priority,
            "topics": topics,
            "status": "error",
            "error": f"Unknown source: {source_id}",
            "count": 0,
            "articles": [],
        }
    
    try:
        articles = fetcher(limit)
        
        for article in articles:
            article["topics"] = topics[:]
        
        return {
            "source_id": source_id,
            "source_type": "crawler",
            "name": name,
            "priority": priority,
            "topics": topics,
            "status": "ok",
            "count": len(articles),
            "articles": articles,
        }
    except Exception as e:
        return {
            "source_id": source_id,
            "source_type": "crawler",
            "name": name,
            "priority": priority,
            "topics": topics,
            "status": "error",
            "error": str(e)[:100],
            "count": 0,
            "articles": [],
        }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch news from web crawlers and API sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--defaults",
        type=Path,
        default=Path("config/defaults"),
        help="Default configuration directory"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        help="User configuration directory for overlays"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Max items per source (default: 15)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output JSON path"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Time window in hours (ignored for crawler sources - they fetch real-time hot items)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch (ignored for crawler sources)"
    )
    
    args = parser.parse_args()
    logger = setup_logging(args.verbose)
    
    if not args.output:
        fd, temp_path = tempfile.mkstemp(prefix="tech-news-digest-crawler-", suffix=".json")
        os.close(fd)
        args.output = Path(temp_path)
    
    try:
        sources = load_crawler_sources(args.defaults, args.config)
        
        logger.info(f"Fetching {len(sources)} crawler sources")
        
        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_source, source, args.limit): source for source in sources}
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                
                if result["status"] == "ok":
                    logger.debug(f"✅ {result['name']}: {result['count']} articles")
                else:
                    logger.debug(f"❌ {result['name']}: {result.get('error', 'unknown error')}")
        
        results.sort(key=lambda x: (not x.get("priority", False), -x.get("count", 0)))
        
        ok_count = sum(1 for r in results if r["status"] == "ok")
        total_articles = sum(r.get("count", 0) for r in results)
        
        output = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "source_type": "crawler",
            "defaults_dir": str(args.defaults),
            "config_dir": str(args.config) if args.config else None,
            "sources_total": len(results),
            "sources_ok": ok_count,
            "total_articles": total_articles,
            "sources": results,
        }
        
        with open(args.output, "w", encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Done: {ok_count}/{len(results)} sources ok, {total_articles} articles → {args.output}")
        
        return 0
        
    except Exception as e:
        logger.error(f"💥 Crawler fetch failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
