"""Conservative collector: only explicit schema.org exhibition events; never infer dates."""
import json, re, urllib.request, hashlib, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
ROOT=Path(__file__).parent
SOURCES=[('東京国立博物館','https://www.tnm.jp/'),('国立西洋美術館','https://www.nmwa.go.jp/'),('東京都美術館','https://www.tobikan.jp/'),('国立新美術館','https://www.nact.jp/'),('東京国立近代美術館','https://www.momat.go.jp/'),('太田記念美術館','https://www.ukiyoe-ota-muse.jp/'),('根津美術館','https://www.nezu-muse.or.jp/'),('ヨックモックミュージアム','https://yokumokumuseum.com/'),('竹久夢二美術館','https://www.yayoi-yumeji-museum.jp/'),('横浜美術館','https://yokohama.art.museum/'),('神奈川県立近代美術館','https://www.moma.pref.kanagawa.jp/'),('岡田美術館','https://www.okada-museum.com/'),('ポーラ美術館','https://www.polamuseum.or.jp/')]
class Parser(HTMLParser):
 def __init__(self): super().__init__(); self.active=False; self.parts=[]; self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='script' and a.get('type')=='application/ld+json': self.active=True; self.parts.append('')
  if tag=='a' and a.get('href'): self.links.append(a['href'])
 def handle_endtag(self,tag):
  if tag=='script': self.active=False
 def handle_data(self,d):
  if self.active:self.parts[-1]+=d

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from walk(v)
 elif isinstance(x,list):
  for v in x:yield from walk(v)
def fetch(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PersonalArtNotebook/1.0'}),timeout=15) as r: raw=r.read(3000000).decode(r.headers.get_content_charset() or 'utf-8',errors='replace')
 p=Parser();p.feed(raw);return p
old=json.loads((ROOT/'exhibitions.json').read_text()); records={x['source']:x for x in old.get('shows',[])}; report=[]
for museum,base in SOURCES:
 found=0
 try:
  p=fetch(base); pages=[(base,p)]
  urls=list(dict.fromkeys(urljoin(base,u) for u in p.links if re.search(r'exhibition|exhibit|exhibitions|tenran',u,re.I)))
  from urllib.parse import urlsplit
  for u in [u for u in urls if urlsplit(u).netloc==urlsplit(base).netloc][:8]:
   try:pages.append((u,fetch(u)))
   except Exception:pass
  for url,p in pages:
   for part in p.parts:
    try: nodes=walk(json.loads(part))
    except ValueError:continue
    for x in nodes:
     typ=x.get('@type',[]);typ=[typ] if isinstance(typ,str) else typ
     if not isinstance(typ,list) or not any(t in ('ExhibitionEvent','https://schema.org/ExhibitionEvent') for t in typ):continue
     title=x.get('name'); start=str(x.get('startDate',''))[:10];end=str(x.get('endDate',''))[:10]
     try: assert isinstance(title,str) and title and datetime.date.fromisoformat(start)<=datetime.date.fromisoformat(end)
     except (ValueError,AssertionError):continue
     target=urljoin(url,x.get('url') or url); key=hashlib.sha256(f'{museum}|{title}|{start}'.encode()).hexdigest();records[key]={'source':key,'title':title,'museum':museum,'start':start,'end':end,'url':target};found+=1
  report.append({'museum':museum,'found':found,'status':'ok' if found else 'no structured exhibitions found'})
 except Exception as e:report.append({'museum':museum,'found':found,'status':str(e)[:150]})
(ROOT/'exhibitions.json').write_text(json.dumps({'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'shows':list(records.values()),'report':report},ensure_ascii=False,indent=2))
