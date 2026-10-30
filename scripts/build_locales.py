"""Собрать статическую RU-страницу из EN-разметки и существующего словаря.

Зависимости: pip install -r scripts/requirements-build.txt
После изменения index.html, content.js или config.js повторить сборку.
"""
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'

def replace_html(element, value):
    element.clear()
    fragment = BeautifulSoup(value, 'html.parser')
    for child in list(fragment.contents):
        element.append(child.extract())

def build():
    raw = (SITE / 'assets/content.js').read_text(encoding='utf-8')
    copy = json.loads(raw[raw.index('{'):].strip().removesuffix(';'))
    soup = BeautifulSoup((SITE / 'index.html').read_text(encoding='utf-8'), 'html.parser')
    soup.html['lang'] = 'ru'
    for key, values in copy.items():
        element = soup.find(id=key)
        if element:
            replace_html(element, values['ru'])
    for element in soup.select('[data-copy]'):
        replace_html(element, copy[element['data-copy']]['ru'])
    replace_html(soup.find(id='h1'), '<span class="hero-word-mask"><span class="hero-word">DENGI</span></span><span class="hero-word-mask"><span class="hero-word accent">MARKET</span></span>')
    paragraphs = soup.select('#heroSub p')
    replace_html(soup.find(id='companyCopy'), ''.join(str(p) for p in paragraphs[1:2]))
    replace_html(soup.find(id='companyContext'), ''.join(str(p) for p in paragraphs[2:]))
    for paragraph in paragraphs[1:]:
        paragraph.decompose()
    if paragraphs:
        lead = re.sub(r'^Dengi Market\s*-\s*', '', paragraphs[0].get_text()).strip()
        lead = lead[0].upper() + lead[1:]
        sentence, divider, rest = lead.partition('. ')
        replace_html(paragraphs[0], '<span class="hero-sub-line">'+sentence+('.' if divider else '')+'</span> '+rest)
    for i,p in enumerate(soup.select('#companyContext p')):
        icon = BeautifulSoup(f'<svg class="context-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-{"wallet" if i==0 else "target"}"></use></svg>', 'html.parser')
        p.insert(0,icon.svg)
    for details in soup.select('[data-content-key]'):
        heading = soup.find(id=details['data-content-key']).find('h3')
        if heading:
            replace_html(details.select_one('.summary-title'), heading.decode_contents())
    config = (SITE / 'assets/config.js').read_text(encoding='utf-8')
    # Берём только существующие значения двух словарей; ничего не переводим.
    names = re.findall(r"name:\s*\{\s*en:\s*'[^']*',\s*ru:\s*'([^']*)'", config)
    roles = re.findall(r"role:\s*\{\s*en:\s*'[^']*',\s*ru:\s*'([^']*)'", config)
    cards = soup.select('.team-card')
    assert len(cards) == len(names) == len(roles), 'Team configuration format changed'
    for card,name,role in zip(cards,names,roles):
        card.h3.string=name; card.h3['lang']='ru'
        card.select_one('.team-role').string=role; card.select_one('.team-role')['lang']='ru'
        card.img['alt']=name; card.img['lang']='ru'
    for element in soup.select('[data-localized-value]'):
        element.string=element['data-ru-value']
    for link in soup.select('[data-language]'):
        if link['data-language']=='ru':
            link['class']=['active']; link['aria-current']='page'
        else:
            link.attrs.pop('aria-current',None); link.attrs.pop('class',None)
    for selector,key in [('.site-nav','primaryNavigation'),('.ir-subnav','investorNavigation'),('.locale','languageSelection'),('#tlPrev','previousEvent'),('#tlNext','nextEvent')]:
        soup.select_one(selector)['aria-label']=copy[key]['ru']
    soup.select_one('.hero-art img')['alt']=copy['heroAlt']['ru']
    soup.find(id='investor-current').string=copy['nav2']['ru']
    for link in soup.select('[data-document-action]'):
        key='openDocument' if link['data-document-action']=='open' else 'downloadDocument'
        link['aria-label']=copy[key]['ru']+' — '+re.search(r'\d{4}',link['href'])[0]
    soup.title.string=copy['seoTitle']['ru']
    soup.select_one('meta[name="description"]')['content']=copy['seoDescription']['ru']
    soup.select_one('meta[property="og:title"]')['content']=copy['seoTitle']['ru']
    soup.select_one('meta[property="og:description"]')['content']=copy['seoDescription']['ru']
    soup.select_one('meta[property="og:locale"]')['content']='ru_RU'
    canonical=soup.select_one('link[hreflang="ru"]')['href']
    soup.select_one('link[rel="canonical"]')['href']=canonical
    soup.select_one('meta[property="og:url"]')['content']=canonical
    (SITE/'index.ru.html').write_text(str(soup),encoding='utf-8')
    base=soup.select_one('link[hreflang="en"]')['href']
    (SITE/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join('<url><loc>'+url+'</loc></url>\n' for url in [base,canonical])+'</urlset>\n',encoding='utf-8')
    print('Built static RU version and sitemap (2 canonical URLs)')

if __name__ == '__main__':
    build()
