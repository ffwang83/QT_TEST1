import json, re, hashlib, os
from datetime import date, timedelta, datetime
from urllib.request import Request, urlopen

API='https://pcc-api.openfun.app/api/listbydate?date={}'
OUT='fontan-radar/data/tenders.json'
RUN='fontan-radar/data/radar-run.json'

POS=['政策宣導','政策溝通','整合行銷','品牌','品牌形象','行銷','媒體','公關','社群','內容','影音','影像','採訪','論壇','策展','觀光','地方創生','產業推廣','產業行銷','青年','文化','活動','人才培訓']
NEG=['道路','橋梁','土木','營造','清潔','保全','設備採購','機電','空調','消防','工程','車輛','物資採購','純印刷']
TYPE_KEYS={
 '政策溝通':['政策','宣導','公共關係','公關','議題','形象'],
 '產業推廣':['產業','招商','企業','創新','創業','品牌推廣'],
 '活動策展':['論壇','活動','展覽','策展','峰會','研討會'],
 '媒體內容':['媒體','新聞','社群','影音','影片','內容','採訪'],
 '地方創生':['地方創生','觀光','旅遊','地方品牌','社區','文化']}

def get_json(url):
    req=Request(url,headers={'User-Agent':'FONTAN-Government-Tender-Radar/1.0'})
    with urlopen(req,timeout=45) as r: return json.loads(r.read().decode('utf-8'))

def text_score(text,budget=0):
    pos=sum(3 for k in POS if k in text)
    neg=sum(7 for k in NEG if k in text)
    s=min(45,45+pos-neg)
    if 80<=budget<=300: s+=15
    elif budget>300: s+=8
    elif 0<budget<50: s-=10
    return max(0,min(100,s))

def classify(text):
    scores={k:sum(1 for x in v if x in text) for k,v in TYPE_KEYS.items()}
    return max(scores,key=scores.get) if max(scores.values(),default=0) else '政策溝通'

def parse_money(x):
    if x is None:return 0
    m=re.search(r'([0-9,.]+)',str(x).replace(',',''))
    return float(m.group(1)) if m else 0

def normalize(r,day):
    brief=r.get('brief') or {}
    title=brief.get('title') or r.get('title') or ''
    agency=r.get('unit_name') or r.get('agency') or ''
    no=r.get('job_number') or r.get('procurement_no') or ''
    detail=r.get('detail') or {}
    raw=' '.join(str(v) for v in detail.values())
    text=' '.join([title,agency,raw])
    budget=parse_money(detail.get('預算金額') or detail.get('預算') or r.get('budget'))
    fit=text_score(text,budget)
    neg=[k for k in NEG if k in text]
    pos=[k for k in POS if k in text]
    decision='排除' if len(neg)>=2 or fit<55 else ('保留' if fit>=80 else '研究')
    rid=hashlib.sha256(f'{no}|{agency}|{title}'.encode()).hexdigest()[:20]
    return {'id':rid,'procNo':no,'title':title,'agency':agency,'budget':budget,'posted':day,'deadline':detail.get('截止投標時間') or detail.get('截止日期') or '', 'type':classify(text),'fit':fit,'decision':decision,'positiveSignals':pos[:8],'negativeSignals':neg[:8],'source':'PCC-derived OpenFun API','sourceUrl':detail.get('url') or r.get('url') or '', 'raw':r}

def main():
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    old=[]
    if os.path.exists(OUT):
        try: old=json.load(open(OUT,encoding='utf-8'))
        except: old=[]
    byid={x['id']:x for x in old}
    today=date.today()
    fetched=[]; errors=[]
    for i in range(7):
        d=(today-timedelta(days=i)).isoformat().replace('-','')
        try:
            ret=get_json(API.format(d))
            for r in ret.get('records',[]):
                x=normalize(r,d)
                if x['title']:
                    byid[x['id']]=x; fetched.append(x['id'])
        except Exception as e: errors.append({'date':d,'error':str(e)})
    rows=list(byid.values())
    rows.sort(key=lambda x:(-x.get('fit',0),x.get('posted','')))
    json.dump(rows,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    run={'runAt':datetime.now().astimezone().isoformat(),'days':7,'fetchedUnique':len(set(fetched)),'totalStored':len(rows),'errors':errors,'source':'https://pcc-api.openfun.app/'}
    json.dump(run,open(RUN,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(run,ensure_ascii=False))

if __name__=='__main__': main()
