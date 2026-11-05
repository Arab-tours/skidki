import re,json,glob,statistics,sys
SRC=sys.argv[1]; OUT=sys.argv[2]
TYPES=[ # prefix, label, cat
('nizkie-krossovki--kedy','Низкие кроссовки','sneakers'),('vysokie-krossovki--kedy','Высокие кроссовки','sneakers'),
('krossovki','Кроссовки','sneakers'),('kedy','Кеды','sneakers'),('slipony','Слипоны','sneakers'),
('sumka-s-korotkimi-ruchkami','Сумка с короткими ручками','bags'),('sumka-tout','Сумка-тоут','bags'),
('sumka-cherez-plecho','Сумка через плечо','bags'),('klatchvechernyaya-sumka','Клатч','bags'),('dorozhnayasportivnaya-sumka','Дорожная сумка','bags'),
('pukhovik','Пуховик','outer'),('kurtka','Куртка','outer'),('palto','Пальто','outer'),('trench--plashch','Тренч','outer'),
('dublenkashuba','Дублёнка','outer'),('zhiletka','Жилет','clothes'),('zhilet','Жилет','outer'),
('dzhemper--sviter','Джемпер','clothes'),('kardigan','Кардиган','clothes'),('vodolazka','Водолазка','clothes'),
('polo-s-dlinnym-rukavom','Поло с длинным рукавом','clothes'),('polo-s-korotkim-rukavom','Поло','clothes'),
('povsednevnye-bryuki','Брюки','clothes'),('pidzhak','Пиджак','clothes'),('klassicheskiy-kostyum','Костюм','clothes'),
('sportivnyy-kostyum','Спортивный костюм','clothes'),('futbolka','Футболка','clothes'),('khuditolstovka','Худи','clothes'),
('pryamye-dzhinsy','Джинсы','clothes'),('dzhinsy-slim','Джинсы','clothes'),('shorty','Шорты','clothes'),('yubka-midi','Юбка','clothes'),
('povsednevnoe-plate','Платье','clothes'),('kokteylnoe-plate','Платье','clothes'),
('botilony','Ботильоны','shoes'),('sabo','Сабо','shoes'),('sandalii','Сандалии','shoes'),('baletki','Балетки','shoes'),
('tufli','Туфли','shoes'),('lofery','Лоферы','shoes'),('botinki','Ботинки','shoes'),('sapogi','Сапоги','shoes'),
('bosonozhki','Босоножки','shoes'),('broggi-i-oksfordy','Броги','shoes'),
('koshelek','Кошелёк','acc'),('remen','Ремень','acc')]
LET=['XXS','XS','S','M','L','XL','XXL','3XL','4XL']
IT_M={44:'XS',46:'S',48:'M',50:'L',52:'XL',54:'XXL',56:'3XL',58:'4XL',60:'4XL',62:'4XL'}
IT_W={36:'XXS',38:'XS',40:'S',42:'M',44:'L',46:'XL',48:'XXL',50:'3XL'}
FR_W={32:'XXS',34:'XS',36:'S',38:'M',40:'L',42:'XL',44:'XXL',46:'3XL'}
RU_W={40:'XXS',42:'XS',44:'S',46:'M',48:'L',50:'XL',52:'XXL'}
def letters(sz,g):
    m=re.match(r'([A-Z_]+)\s+(.*)',sz or '');
    if not m: return []
    sys_,vals=m.group(1),[v.strip() for v in m.group(2).split('/')]
    out=[]
    for v in vals:
        if sys_=='INT':
            v=v.replace('2XS','XXS').replace('2XL','XXL')
            if v in LET: out.append(v)
            continue
        try: n=float(v.replace(',','.'))
        except: continue
        n=int(n)
        if sys_=='JEANS': out.append({30:'S',31:'S',32:'M',33:'L',34:'L',36:'XL'}.get(n))
        elif sys_=='US': out.append({0:'XXS',2:'XS',4:'S',6:'M',8:'L',10:'XL'}.get(n))
        elif g=='m': out.append(IT_M.get(n))
        elif sys_ in('FR','EU'): out.append(FR_W.get(n))
        elif sys_=='RU': out.append(RU_W.get(n))
        else: out.append(IT_W.get(n))
    return sorted({x for x in out if x},key=LET.index)
def shoes(sz):
    m=re.match(r'([A-Z]+)\s+(.*)',sz or '')
    if not m: return []
    s,vals=m.group(1),m.group(2).split('/')
    out=[]
    for v in vals:
        try: n=float(v.strip().replace(',','.'))
        except: continue
        if s=='UK': n+=34
        elif s=='US': n+=33
        elif s=='RU': n+=1
        out.append(n)
    return sorted(set(out))
items=[];skipped=0
for f in sorted(glob.glob(SRC+'/*.txt')):
    brand=g=cat0=None
    for line in open(f,encoding='utf8'):
        line=line.strip()
        if not line: continue
        if line.startswith('#'):
            brand,g,cat0=line[1:].split('|');continue
        slug,p,o,sz,img=line.split('|')
        pid=int(slug.rsplit('-',1)[1])
        if pid<1000000: skipped+=1;continue
        t=next(((lab,c) for pre,lab,c in TYPES if slug.startswith(pre+'-')),None)
        if not t: skipped+=1;continue
        lab,cat=t
        cond='used' if '-pre-owned-' in slug else 'new'
        sz='' if sz in('-','INT U','One size') else sz
        it={'id':pid,'b':brand,'g':g,'c':cat,'t':lab,'p':int(p),'o':int(o) if o!='-' else None,'k':cond,'s':sz,
            'u':'https://oskelly.ru/products/'+slug,'i':img if img!='-' else ''}
        if cat in('outer','clothes'): it['L']=letters(sz,g)
        if cat in('shoes','sneakers'): it['E']=shoes(sz)
        if it['o'] and it['o']<=it['p']: it['o']=None
        items.append(it)
# dedupe
seen=set();uniq=[]
for it in items:
    if it['id'] in seen: continue
    seen.add(it['id']);uniq.append(it)
items=uniq
# medians
from collections import defaultdict
grp=defaultdict(list)
for it in items: grp[(it['b'],it['t'],it['k'])].append(it['p'])
grp2=defaultdict(list)
for it in items: grp2[(it['b'],it['c'],it['k'])].append(it['p'])
for it in items:
    a=grp[(it['b'],it['t'],it['k'])]
    if len(a)>=5:
        m=statistics.median(a); it['m']=int(round(m,-2)); it['v']=round((1-it['p']/m)*100)
json.dump({'updatedAt':'2026-11-05','source':'Oskelly','items':items},open(OUT,'w'),ensure_ascii=False,separators=(',',':'))
from collections import Counter
print(len(items),'skipped',skipped)
print(Counter(i['b'] for i in items))
print(Counter(i['c'] for i in items))
print('no letters', sum(1 for i in items if i['c'] in('outer','clothes') and not i['L']), 'no shoe', sum(1 for i in items if i['c'] in('shoes','sneakers') and not i['E']))
