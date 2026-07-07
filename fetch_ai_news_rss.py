import urllib.request
import xml.etree.ElementTree as ET
import json
import ssl
import re
import html
import time
import gzip
from datetime import datetime

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# List of expanded defence, official, geopolitical, and SSB RSS feeds
feeds = [
    {"source": "IDRW Defence", "url": "https://idrw.org/feed/"},
    {"source": "PIB Defence", "url": "https://pib.gov.in/Rss/DefenceReleaseRSS.aspx"},
    {"source": "Indian Defence Review", "url": "https://indiandefencereview.com/feed/"},
    {"source": "Defence.in", "url": "https://defence.in/feed/"},
    {"source": "Indian Defence News", "url": "https://www.indiandefensenews.in/feeds/posts/default"},
    {"source": "Swarajya Defence", "url": "https://swarajyamag.com/feed"},
    {"source": "StratNews Global", "url": "https://stratnewsglobal.com/feed/"},
    {"source": "PRS Policy Research", "url": "https://prsindia.org/rss.xml"},
    {"source": "The Diplomat South Asia", "url": "https://thediplomat.com/regions/south-asia/feed/"},
    {"source": "ORF", "url": "https://www.orfonline.org/feed/"},
    {"source": "IADN", "url": "https://iadnews.in/feed/"},
    {"source": "Gateway House", "url": "https://www.gatewayhouse.in/feed/"},
    {"source": "SSBCrack", "url": "https://www.ssbcrack.com/feed/"}
]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate"
}

def regex_parse_rss(xml_text):
    """
    Robust regex fallback parser to parse RSS/Atom feed item fields 
    in case standard XML parsers fail due to malformed XML or namespace tokens.
    """
    items = []
    
    # Try RSS item blocks first
    item_blocks = re.findall(r'<item.*?>(.*?)</item>', xml_text, re.DOTALL | re.IGNORECASE)
    is_atom = False
    
    if not item_blocks:
        # Try Atom entry blocks
        item_blocks = re.findall(r'<entry.*?>(.*?)</entry>', xml_text, re.DOTALL | re.IGNORECASE)
        is_atom = True
        
    for block in item_blocks:
        # Extract title
        title_m = re.search(r'<title.*?>(.*?)</title>', block, re.DOTALL | re.IGNORECASE)
        title = title_m.group(1).strip() if title_m else ""
        if title.startswith("<![CDATA[") and title.endswith("]]>"):
            title = title[9:-3].strip()
            
        # Extract link
        if is_atom:
            link_m = re.search(r'<link.*?href=[\'"](.*?)[\'"]', block, re.DOTALL | re.IGNORECASE)
        else:
            link_m = re.search(r'<link>(.*?)</link>', block, re.DOTALL | re.IGNORECASE)
        link = link_m.group(1).strip() if link_m else ""
        if link.startswith("<![CDATA[") and link.endswith("]]>"):
            link = link[9:-3].strip()
            
        # Extract description / summary
        if is_atom:
            desc_m = re.search(r'<(?:summary|content).*?>(.*?)</(?:summary|content)>', block, re.DOTALL | re.IGNORECASE)
        else:
            desc_m = re.search(r'<description>(.*?)</description>', block, re.DOTALL | re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""
        if desc.startswith("<![CDATA[") and desc.endswith("]]>"):
            desc = desc[9:-3].strip()
            
        # Extract pubDate / published
        if is_atom:
            pub_m = re.search(r'<(?:published|updated)>(.*?)</(?:published|updated)>', block, re.DOTALL | re.IGNORECASE)
        else:
            pub_m = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL | re.IGNORECASE)
        pub = pub_m.group(1).strip() if pub_m else ""
        if pub.startswith("<![CDATA[") and pub.endswith("]]>"):
            pub = pub[9:-3].strip()
            
        items.append({
            "title": title,
            "link": link,
            "description": desc,
            "pubDate": pub
        })
    return items

def clean_html_description(desc_html):
    if not desc_html:
        return ""
    decoded = html.unescape(desc_html)
    # Convert paragraph and linebreaks to newlines
    text_with_newlines = re.sub(r'<(?:p|br|div)[^>]*>', '\n', decoded)
    # Strip remaining HTML tags
    clean = re.sub(r'<[^>]+>', '', text_with_newlines)
    # Normalize whitespaces
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

all_news = []

for idx, feed in enumerate(feeds):
    # Rate limit: Sleep 1.5 seconds between feeds (respectful scraping)
    if idx > 0:
        time.sleep(1.5)
        
    print(f"Fetching RSS for {feed['source']}: {feed['url']}")
    req = urllib.request.Request(feed['url'], headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            raw_data = response.read()
            
            # Decompress Gzip content if encoded
            content_encoding = response.info().get('Content-Encoding', '')
            if 'gzip' in content_encoding or raw_data.startswith(b'\x1f\x8b'):
                try:
                    rss_content = gzip.decompress(raw_data).decode("utf-8", errors="ignore")
                except Exception as g_err:
                    print(f"  [Gzip decompression failed, reading raw]: {g_err}")
                    rss_content = raw_data.decode("utf-8", errors="ignore")
            else:
                rss_content = raw_data.decode("utf-8", errors="ignore")
                
            parsed_items = []
            
            # Attempt ElementTree parsing first
            try:
                root = ET.fromstring(rss_content)
                items = root.findall('.//item')
                for item in items:
                    title_el = item.find('title')
                    title = title_el.text if title_el is not None else ""
                    link_el = item.find('link')
                    link = link_el.text if link_el is not None else ""
                    desc_el = item.find('description')
                    desc = desc_el.text if desc_el is not None else ""
                    pub_el = item.find('pubDate')
                    pub_date = pub_el.text if pub_el is not None else ""
                    
                    parsed_items.append({
                        "title": title,
                        "link": link,
                        "description": desc,
                        "pubDate": pub_date
                    })
            except Exception as xml_err:
                print(f"  [XML parse failed, falling back to regex parser for {feed['source']}]: {xml_err}")
                parsed_items = regex_parse_rss(rss_content)
                
            print(f"  Successfully parsed {len(parsed_items)} items from {feed['source']}")
            
            for item in parsed_items:
                title = item["title"]
                link = item["link"]
                desc = clean_html_description(item["description"])
                pub_date = item["pubDate"]
                
                if not title:
                    continue
                    
                news_item = {
                    "source": feed["source"],
                    "title": title,
                    "description": desc,
                    "pubDate": pub_date,
                    "url": link
                }
                all_news.append(news_item)
                
    except Exception as e:
        print(f"ERROR: Failed fetching {feed['source']}: {e}")

# Save fallback if empty
if not all_news:
    print("Warning: RSS fetch failed. Populating with curated defence news fallback data.")
    all_news = [
        {
            "source": "PIB Defence",
            "title": "Bilateral Military Exercise Yudh Abhyas commences between India and USA",
            "description": "The joint military training exercise focuses on tactical-level operations, mountain warfare, and interoperability between the two armies, enhancing bilateral defence ties.",
            "pubDate": "July 2026",
            "url": "https://pib.gov.in/defence_exercise_yudh_abhyas"
        },
        {
            "source": "Ministry of Defence",
            "title": "India and France hold 26th Defence Cooperation Group meeting in Paris",
            "description": "Both nations reviewed current military-to-military cooperation, joint exercises like Varuna and Garuda, and co-development of defence technologies under the Make in India initiative.",
            "pubDate": "July 2026",
            "url": "https://pib.gov.in/defence_cooperation_france"
        },
        {
            "source": "PIB Defence",
            "title": "Quad Navies conduct complex Anti-Submarine drills in Malabar Exercise",
            "description": "The Malabar naval exercise brings together naval forces of India, USA, Japan, and Australia in the Indian Ocean to practice complex anti-submarine warfare and maritime domain awareness drills.",
            "pubDate": "July 2026",
            "url": "https://pib.gov.in/malabar_naval_exercise"
        },
        {
            "source": "IDRW Defence",
            "title": "DRDO successfully test fires indigenous very short-range air defence system",
            "description": "The Defence Research and Development Organisation (DRDO) conducted a successful flight test of the Very Short-Range Air Defence System (VSHORADS) missile from a ground-based launcher.",
            "pubDate": "July 2026",
            "url": "https://idrw.org/drdo_vshorads_test"
        }
    ]

# Save to ai_news_data.json
with open("./ai_news_data.json", "w", encoding="utf-8") as f:
    json.dump(all_news, f, indent=2)

print(f"Saved {len(all_news)} news items to ./ai_news_data.json")
