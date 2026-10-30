"""Локальная проверка индексируемых EN/RU-страниц, метаданных и ссылок."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import json
import xml.etree.ElementTree as ET

SITE = Path(__file__).resolve().parents[1] / 'site'

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.tags=[]; self.text=[]
        self.feed(path.read_text(encoding='utf-8'))
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag,dict(attrs)))
    def handle_data(self, data):
        self.text.append(data)
    def elements(self, tag, **attrs):
        return [a for t,a in self.tags if t==tag and all(a.get(k)==v for k,v in attrs.items())]

canonical=[]
for name,language in [('index.html','en'),('index.ru.html','ru')]:
    path=SITE/name; page=Page(path)
    assert page.elements('html',lang=language)
    assert len(page.elements('h1'))==1
    assert len(page.elements('title'))==1
    assert page.elements('meta',name='description')[0]['content']
    assert 'noindex' not in page.elements('meta',name='robots')[0]['content']
    url=page.elements('link',rel='canonical')[0]['href']
    canonical.append(url)
    alternates={a['hreflang']:a['href'] for a in page.elements('link',rel='alternate')}
    assert set(alternates)=={'en','ru','x-default'} and alternates[language]==url
    assert page.elements('meta',property='og:url')[0]['content']==url
    assert page.elements('meta',property='og:description')[0]['content']==page.elements('meta',name='description')[0]['content']
    ids=[a['id'] for _,a in page.tags if 'id' in a]
    assert len(ids)==len(set(ids)),f'Duplicate IDs: {name}'
    for tag,attrs in page.tags:
        if tag=='img':
            assert 'alt' in attrs,attrs
        for key in ('href','src'):
            value=attrs.get(key,'')
            if value.startswith(('#','mailto:','data:')) or not value or urlsplit(value).scheme:
                continue
            target=SITE/urlsplit(value).path
            assert target.is_file() or (target/'index.html').is_file(),(name,value)
    assert 'info@dengiclick.kz' not in path.read_text(encoding='utf-8')
    assert page.elements('a',href='mailto:investors@dengimarket-ir.com')
    assert ('Информация для инвесторов' if language=='ru' else 'Investor Relations') in ''.join(page.text)
    print(f'PASS {name}: metadata, language, links, {len(ids)} unique IDs, contact')
urls=[node.text for node in ET.parse(SITE/'sitemap.xml').findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
assert urls==canonical
for name in ('articles','article','admin'):
    assert 'noindex' in Page(SITE/name/'index.html').elements('meta',name='robots')[0]['content']
print('PASS sitemap: two canonical URLs; unready editorial pages and admin are noindex')
