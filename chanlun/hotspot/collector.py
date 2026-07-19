# -*- coding: utf-8 -*-
"""
热点信息统一采集入口
数据源: 微博热搜、百度热搜、东方财富概念板块、政策源(央行/发改委/东方财富新闻)
"""
import requests
import re
import time
import traceback
from datetime import datetime
from typing import List, Dict, Any


class BaseCrawler:
    """采集器基类"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.timeout = 15

    def fetch(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def _make_item(self, source: str, title: str, hot_score: int = 0,
                   url: str = '', category: str = 'general',
                   extra: Dict = None) -> Dict[str, Any]:
        return {
            'source': source,
            'title': title.strip(),
            'hot_score': hot_score,
            'url': url,
            'category': category,
            'extra': extra or {},
        }


class WeiboCrawler(BaseCrawler):
    """微博热搜采集"""

    URL = 'https://weibo.com/ajax/side/hotSearch'

    def fetch(self) -> List[Dict[str, Any]]:
        self.session.headers.update({
            'Referer': 'https://weibo.com/',
            'X-Requested-With': 'XMLHttpRequest',
        })
        resp = self.session.get(self.URL, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        items = []
        realtime = data.get('data', {}).get('realtime', [])
        for idx, entry in enumerate(realtime, 1):
            title = entry.get('word', '') or entry.get('note', '')
            if not title:
                continue
            hot_score = entry.get('raw_hot', 0) or entry.get('num', 0) or 0
            label_name = entry.get('label_name', '')
            category = self._classify_label(label_name)
            url = f"https://s.weibo.com/weibo?q=%23{title}%23"
            items.append(self._make_item(
                source='weibo',
                title=title,
                hot_score=int(hot_score),
                url=url,
                category=category,
                extra={'rank': idx, 'label': label_name, 'icon_desc': entry.get('icon_desc', '')},
            ))
        return items

    def _classify_label(self, label: str) -> str:
        if label in ('新', '热', '沸', '爆'):
            return 'general'
        if label == '影':
            return 'entertainment'
        return 'general'


class BaiduCrawler(BaseCrawler):
    """百度热搜采集"""

    URL = 'https://top.baidu.com/api/board?platform=wise&tab=realtime'

    def fetch(self) -> List[Dict[str, Any]]:
        self.session.headers.update({
            'Referer': 'https://top.baidu.com/',
        })
        resp = self.session.get(self.URL, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        items = []
        cards = data.get('data', {}).get('cards', [])
        for card in cards:
            # 百度热搜content是嵌套结构: cards[].content[].content[]
            raw_content = card.get('content', [])
            entries = []
            for item in raw_content:
                if isinstance(item, dict) and 'content' in item:
                    entries.extend(item['content'])
                elif isinstance(item, dict):
                    entries.append(item)
            for idx, entry in enumerate(entries, 1):
                title = entry.get('word', '') or entry.get('query', '')
                if not title:
                    continue
                hot_score = int(entry.get('hotScore', 0) or entry.get('rawUrl', '').split('hotScore=')[-1].split('&')[0] or 0)
                url = entry.get('url', '') or entry.get('rawUrl', '')
                desc = entry.get('desc', '')
                items.append(self._make_item(
                    source='baidu',
                    title=title,
                    hot_score=hot_score,
                    url=url,
                    category='general',
                    extra={'rank': idx, 'desc': desc[:200], 'img': entry.get('img', '')},
                ))
        return items


class EastMoneyCrawler(BaseCrawler):
    """东方财富概念板块采集"""

    URL = ('http://80.push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1'
           '&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3'
           '&fs=m:90+t:3&fields=f2,f3,f12,f14,f62,f104,f105')

    def fetch(self) -> List[Dict[str, Any]]:
        resp = self.session.get(self.URL, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        items = []
        diff = data.get('data', {}).get('diff', [])
        if isinstance(diff, dict):
            diff = list(diff.values())
        for idx, entry in enumerate(diff, 1):
            board_code = entry.get('f12', '')
            board_name = entry.get('f14', '')
            if not board_name:
                continue
            change_pct = entry.get('f3', 0)  # 涨跌幅
            net_inflow = entry.get('f62', 0)  # 净流入
            up_count = entry.get('f104', 0)   # 上涨数
            down_count = entry.get('f105', 0) # 下跌数
            price = entry.get('f2', 0)

            items.append(self._make_item(
                source='eastmoney_concept',
                title=board_name,
                hot_score=int(abs(net_inflow / 10000)) if net_inflow else 0,
                url=f'https://quote.eastmoney.com/concept/{board_code}.html',
                category='finance',
                extra={
                    'board_code': board_code,
                    'change_pct': change_pct,
                    'net_inflow': net_inflow,
                    'up_count': up_count,
                    'down_count': down_count,
                    'price': price,
                    'rank': idx,
                },
            ))
        return items


class PolicyCrawler(BaseCrawler):
    """
    政策新闻采集 - 多源聚合
    主源: 东方财富财经快讯(JSON API, 实时)
    辅源: 央行公告(pbc.gov.cn), 发改委(ndrc.gov.cn)
    """

    # 东方财富7x24快讯
    EASTMONEY_NEWS_URL = ('https://np-listapi.eastmoney.com/comm/web/getFastNewsList'
                          '?client=web&biz=web_724&fastColumn=102&sortEnd=&'
                          'pageSize=50&req_trace=1')
    # 央行公告
    PBC_URL = 'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html'
    # 发改委政策
    NDRC_URL = 'https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/'

    def fetch(self) -> List[Dict[str, Any]]:
        items = []
        # 主源: 东方财富快讯
        items.extend(self._fetch_eastmoney_news())
        # 辅源: 央行
        items.extend(self._fetch_pbc())
        # 辅源: 发改委
        items.extend(self._fetch_ndrc())
        return items

    def _fetch_eastmoney_news(self) -> List[Dict[str, Any]]:
        """东方财富7x24快讯"""
        try:
            resp = self.session.get(self.EASTMONEY_NEWS_URL, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            items = []
            news_list = data.get('data', {}).get('fastNewsList', [])
            for entry in news_list:
                title = entry.get('title', '')
                if not title:
                    continue
                show_time = entry.get('showTime', '')
                summary = entry.get('summary', '')
                code = entry.get('code', '')
                url = f'https://finance.eastmoney.com/a/{code}.html' if code else ''
                items.append(self._make_item(
                    source='eastmoney_news',
                    title=title,
                    hot_score=0,
                    url=url,
                    category='policy',
                    extra={'show_time': show_time, 'summary': summary[:300]},
                ))
            return items
        except Exception as e:
            print(f"[PolicyCrawler] 东方财富快讯采集失败: {e}")
            return []

    def _fetch_pbc(self) -> List[Dict[str, Any]]:
        """央行公告"""
        try:
            resp = self.session.get(self.PBC_URL, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            items = []
            # 解析: <font class="newslist_style"><a href="..." title="...">...</a></font>
            pattern = r'<font class="newslist_style">\s*<a[^>]+href="([^"]+)"[^>]*title="([^"]+)"'
            matches = re.findall(pattern, html)
            for href, title in matches[:30]:
                if not title.strip():
                    continue
                url = f'http://www.pbc.gov.cn{href}' if href.startswith('/') else href
                # 从路径提取日期
                date_match = re.search(r'(\d{4})(\d{2})(\d{2})', href)
                pub_date = f'{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}' if date_match else ''
                items.append(self._make_item(
                    source='pbc',
                    title=title.strip(),
                    hot_score=0,
                    url=url,
                    category='policy',
                    extra={'pub_date': pub_date},
                ))
            return items
        except Exception as e:
            print(f"[PolicyCrawler] 央行采集失败: {e}")
            return []

    def _fetch_ndrc(self) -> List[Dict[str, Any]]:
        """发改委政策"""
        try:
            resp = self.session.get(self.NDRC_URL, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            html = resp.text
            items = []
            # 解析: <a ... title="...">...</a> + <span>日期</span>
            pattern = r'<a[^>]+href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?</a>\s*<span[^>]*>([^<]*)</span>'
            matches = re.findall(pattern, html, re.DOTALL)
            for href, title, date_str in matches[:30]:
                if not title.strip():
                    continue
                url = f'https://www.ndrc.gov.cn{href}' if href.startswith('/') else href
                if href.startswith('./'):
                    url = f'https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/{href[2:]}'
                items.append(self._make_item(
                    source='ndrc',
                    title=title.strip(),
                    hot_score=0,
                    url=url,
                    category='policy',
                    extra={'pub_date': date_str.strip()},
                ))
            return items
        except Exception as e:
            print(f"[PolicyCrawler] 发改委采集失败: {e}")
            return []


def collect_all() -> Dict[str, List[Dict[str, Any]]]:
    """运行所有采集器"""
    results = {}
    crawlers = {
        'weibo': WeiboCrawler(),
        'baidu': BaiduCrawler(),
        'eastmoney_concept': EastMoneyCrawler(),
        'policy': PolicyCrawler(),
    }
    for name, crawler in crawlers.items():
        start = time.time()
        try:
            items = crawler.fetch()
            duration = int((time.time() - start) * 1000)
            results[name] = {'items': items, 'status': 'success', 'duration_ms': duration}
            print(f"[{name}] 采集成功: {len(items)} 条, 耗时 {duration}ms")
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            results[name] = {'items': [], 'status': 'failed', 'duration_ms': duration, 'error': str(e)}
            print(f"[{name}] 采集失败: {e}")
            traceback.print_exc()
    return results


if __name__ == '__main__':
    results = collect_all()
    total = sum(len(r['items']) for r in results.values())
    print(f"\n=== 采集完成, 总计 {total} 条 ===")
    for name, r in results.items():
        print(f"  {name}: {len(r['items'])} 条 [{r['status']}]")
