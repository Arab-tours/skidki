#!/usr/bin/env python3
"""Сборщик находок «Охота за скидками».

Источники: Oskelly, The Cultt, VIP Avenue (распродажа), Ozon (категории брендов).
Перед каждым запросом проверяется robots.txt сайта (правила для нашего user-agent или «*»,
с поддержкой * и $). Запросы к одному сайту идут последовательно с паузой.

Запуск:  python3 tools/scrape.py data/sources.json deals.json
"""
import urllib.error
import json, re, sys, time, html, statistics, threading, urllib.request, urllib.parse, gzip, zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (compatible; OkhotaZaSkidkami/1.0; +https://github.com/Arab-tours/skidki)"
UA_TOKEN = "okhotazaskidkami"
DELAY = 1.2

# ---------------- http + robots ----------------
_robots = {}
_last = defaultdict(float)
_locks = defaultdict(threading.Lock)

def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9", "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        enc = r.headers.get("Content-Encoding", "")
        if enc == "gzip" or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        elif enc == "deflate":
            data = zlib.decompress(data)
        return r.status, data.decode("utf-8", "replace")

def _parse_robots(txt):
    groups, cur, seen_rule = [], None, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line: continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if cur is None or seen_rule:
                cur = {"agents": [], "rules": []}; groups.append(cur); seen_rule = False
            cur["agents"].append(v.lower())
        elif k in ("allow", "disallow") and cur is not None:
            seen_rule = True
            if v: cur["rules"].append((k == "allow", v))
    mine = [g for g in groups if any(UA_TOKEN in a for a in g["agents"])]
    star = [g for g in groups if "*" in g["agents"]]
    rules = []
    for g in (mine or star): rules += g["rules"]
    return rules

def _rx(pat):
    end = pat.endswith("$")
    p = re.escape(pat[:-1] if end else pat).replace(r"\*", ".*")
    return re.compile("^" + p + ("$" if end else ""))

def allowed(url):
    u = urllib.parse.urlsplit(url)
    host = u.scheme + "://" + u.netloc
    if host not in _robots:
        try:
            st, txt = _get(host + "/robots.txt")
            _robots[host] = _parse_robots(txt) if st == 200 else []
        except Exception:
            _robots[host] = []
    path = u.path + ("?" + u.query if u.query else "")
    best = None
    for allow, pat in _robots[host]:
        if _rx(pat).match(path):
            if best is None or len(pat) > len(best[1]) or (len(pat) == len(best[1]) and allow):
                best = (allow, pat)
    return best is None or best[0]

def fetch(url):
    if not allowed(url):
        log(f"robots: пропуск {url}"); return None
    host = urllib.parse.urlsplit(url).netloc
    with _locks[host]:
        wait = DELAY - (time.time() - _last[host])
        if wait > 0: time.sleep(wait)
        st, body = 0, None
        for attempt in range(2):
            try:
                st, body = _get(url); break
            except urllib.error.HTTPError as e:
                st = e.code; break
            except Exception as e:
                log(f"ошибка {url}: {e}"); time.sleep(3)
        _last[host] = time.time()
    return body if st == 200 else None

def log(m): print(m, file=sys.stderr, flush=True)
def txt(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
def money(s):
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else None

# ---------------- classification ----------------
CAT_WORDS = [
    ("sneakers", ["кроссовк", "кеды", "кед ", "слипон", "сникер"]),
    ("bags", ["сумк", "клатч", "рюкзак", "тоут", "шоппер", "портфел", "саквояж", "кросс-боди", "кросс боди", "баул"]),
    ("acc", ["кошел", "ремень", "ремни", "шарф", "платок", "палантин", "очки", "картхолдер", "визитниц", "брелок", "шапк", "кепк", "перчат", "часы", "браслет", "серьг", "кольц", "колье", "подвеск", "ключниц", "обложк", "косметичк", "галстук"]),
    ("shoes", ["туфл", "ботин", "сапог", "лофер", "балетк", "босонож", "сандал", "мюл", "сабо", "ботильон", "мокасин", "эспадрил", "броги", "оксфорд", "дерби", "шлепан", "сланц", "угги", "ботфорт", "челси"]),
    ("outer", ["пуховик", "куртк", "пальто", "тренч", "плащ", "парк", "дублен", "шуб", "бомбер", "жилет", "анорак", "ветровк", "пуховой"]),
]
def classify(name, hint=None):
    n = (name or "").lower() + " "
    for cat, words in CAT_WORDS:
        if any(w in n for w in words): return cat
    return hint or "clothes"

LET = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL"]
IT_M = {44: "XS", 46: "S", 48: "M", 50: "L", 52: "XL", 54: "XXL", 56: "3XL", 58: "4XL", 60: "4XL", 62: "4XL"}
IT_W = {36: "XXS", 38: "XS", 40: "S", 42: "M", 44: "L", 46: "XL", 48: "XXL", 50: "3XL"}
FR_W = {32: "XXS", 34: "XS", 36: "S", 38: "M", 40: "L", 42: "XL", 44: "XXL", 46: "3XL"}
RU_W = {40: "XXS", 42: "XS", 44: "S", 46: "M", 48: "L", 50: "XL", 52: "XXL"}

def letters(sz, g):
    m = re.match(r"([A-Z_]+)\s+(.*)", sz or "")
    sys_, vals = (m.group(1), m.group(2)) if m else ("IT", sz or "")
    out = []
    for v in re.split(r"[/,;]\s*", vals):
        v = v.strip().upper().replace("2XS", "XXS").replace("2XL", "XXL")
        if v in LET: out.append(v); continue
        try: n = int(float(v.replace(",", ".")))
        except ValueError: continue
        if sys_ == "JEANS": out.append({30: "S", 31: "S", 32: "M", 33: "L", 34: "L", 36: "XL"}.get(n))
        elif sys_ == "US": out.append({0: "XXS", 2: "XS", 4: "S", 6: "M", 8: "L", 10: "XL"}.get(n))
        elif g == "m": out.append(IT_M.get(n))
        elif sys_ in ("FR", "EU"): out.append(FR_W.get(n))
        elif sys_ == "RU": out.append(RU_W.get(n))
        else: out.append(IT_W.get(n))
    return sorted({x for x in out if x}, key=LET.index)

def shoes(sz):
    m = re.match(r"([A-Z]+)\s+(.*)", sz or "")
    s, vals = (m.group(1), m.group(2)) if m else ("EU", sz or "")
    out = []
    for v in re.split(r"[/,;]\s*", vals):
        try: n = float(v.strip().replace(",", "."))
        except ValueError: continue
        if s == "UK": n += 34
        elif s == "US": n += 33
        elif s == "RU": n += 1
        if 33 <= n <= 49: out.append(n)
    return sorted(set(out))

# ---------------- sources ----------------
def src_oskelly(cfg):
    items = []
    for brand, slug in cfg["brands"].items():
        for section in cfg["sections"]:
            url = f"https://oskelly.ru/catalog/{slug}/{section}"
            body = fetch(url)
            if not body: continue
            g = "w" if section.startswith("zhenskoe") else "m" if section.startswith("muzhskoe") else "k"
            hint = {"sumki": "bags", "obuv": "shoes", "aksessuary": "acc"}.get(section.split("/")[1], None)
            for card in body.split('class="osk-product-card"')[1:]:
                card = card.split('class="osk-product-card"')[0]
                m = re.search(r'href="/products/([a-z0-9-]+-(\d+))"', card)
                if not m: continue
                slug_p, pid = m.group(1), int(m.group(2))
                name = txt((re.search(r'card-info-name"[^>]*>(.*?)</div>', card, re.S) or [None, ""])[1])
                size = txt((re.search(r'card-info-size"[^>]*>(.*?)</div>', card, re.S) or [None, ""])[1])
                price = money((re.search(r'price-value"[^>]*>(.*?)</span>', card, re.S) or [None, ""])[1])
                old = money((re.search(r'price-discount"[^>]*>(.*?)</span>', card, re.S) or [None, ""])[1])
                img = (re.search(r'<img[^>]+src="(https://static\.cdn\.oskelly\.ru/product/[^"]+)"', card) or [None, ""])[1]
                if not price: continue
                items.append(dict(id="o" + str(pid), src="Oskelly", b=brand, g=g, t=name or "Вещь", c=classify(name, hint),
                                  p=price, o=old, s=size, k="used" if "-pre-owned-" in slug_p else "new",
                                  u="https://oskelly.ru/products/" + slug_p, i=img, auth=True))
            log(f"oskelly {brand} {section}: всего {len(items)}")
    return items

def src_cultt(cfg):
    items, seen = [], {}
    pages = [(f"https://thecultt.com/catalog/{c}/{s}", b) for b, s in cfg["brands"].items() for c in cfg["categories"]] \
            + [("https://thecultt.com/catalog/sale", None)]
    known = {k.lower().replace("è", "e"): k for k in cfg["brands"]}
    catmap = {"Сумки": "bags", "Обувь": "shoes", "Аксессуары": "acc", "Одежда": "clothes", "Украшения": "acc", "Часы": "acc"}
    def f(chunk, key):
        m = re.search(r'"' + key + r'":("((?:[^"\\]|\\.)*)"|null|true|false|-?\d+(?:\.\d+)?)', chunk)
        if not m: return None
        return m.group(2) if m.group(2) is not None else (None if m.group(1) == "null" else m.group(1))
    for url, want in pages:
        body = fetch(url)
        if not body: continue
        data = body.replace('\\"', '"').replace('\\\\', '\\')
        for chunk in data.split('{"card_type":"product"')[1:]:
            chunk = chunk[:4000]
            art = f(chunk, "article")
            if not art or art in seen: continue
            brand_raw = (f(chunk, "manufacturer") or "").strip()
            brand = known.get(brand_raw.lower().replace("è", "e"))
            if not brand or (want and brand != want): continue
            price = f(chunk, "price"); old = f(chunk, "old_price")
            try: price = int(float(price)); old = int(float(old)) if old else None
            except (TypeError, ValueError): continue
            cat = catmap.get(f(chunk, "category") or "", "acc")
            sub = f(chunk, "subcategory") or ""
            model = (f(chunk, "model_name") or "").strip()
            cond = f(chunk, "condition") or ""
            gender = f(chunk, "gender") or ""
            shoe = f(chunk, "shoe_size"); size = f(chunk, "size")
            imgs = re.findall(r'https://goodscard\.thecultt\.com/\d+/[A-Za-z0-9]+\.(?:jpg|jpeg|png|webp)', chunk)
            if cat == "bags" and any(w in sub.lower() for w in ("кошел", "картхолдер", "визитниц")): cat = "acc"
            it = dict(id="c" + art, src="The Cultt", b=brand, g="m" if gender.startswith("муж") else "w",
                      t=(sub + (" " + model if model else "")).strip() or "Вещь", c=cat, p=price, o=old if old and old > price else None,
                      s=("EU " + str(shoe)) if shoe else (str(size) if size else ""), k="new" if cond.lower().startswith("нов") else "used",
                      cond=cond, mdl=re.sub(r"\s+\d+([,.]\d+)?$", "", model).lower() or None, u="https://thecultt.com/product/" + art, i=imgs[0] if imgs else "", auth=True)
            seen[art] = it; items.append(it)
        log(f"cultt {url}: всего {len(items)}")
    return items

def src_vip(cfg):
    items = []
    lux = {b.lower(): b for b in cfg["brands"]}
    def vslug(b): return re.sub(r"[^a-z0-9]+", "-", b.lower().replace("&", "").replace("'", "").replace("é", "e").replace("è", "e").replace("ï", "i")).strip("-")
    for bname in cfg["brands"]:
      for section, g in (("womens", "w"), ("mens", "m")):
        for page in range(1, cfg.get("pages", 4) + 1):
            url = f"https://www.vipavenue.ru/brands/{section}/{vslug(bname)}/" + (f"?page={page}" if page > 1 else "")
            body = fetch(url)
            if not body: break
            blocks = body.split('<a href="/product/')[1:]
            got = 0
            for b in blocks:
                if 'class="product__content"' not in b[:200]: continue
                m = re.match(r'(\d+)-([a-z0-9-]+)/"', b)
                if not m: continue
                brand_raw = txt((re.search(r'product__brand"[^>]*>(.*?)</div>', b, re.S) or [None, ""])[1])
                name = txt((re.search(r'product__name"[^>]*>(.*?)</div>', b, re.S) or [None, ""])[1])
                old = money((re.search(r'product__price-old"[^>]*>(.*?)</div>', b, re.S) or [None, ""])[1])
                new = money((re.search(r'product__price-new"[^>]*>(.*?)</div>', b, re.S) or [None, ""])[1])
                sizes = [txt(x) for x in re.findall(r'class="product__size"[^>]*>(.*?)</li>', b, re.S)]
                got += 1
                key = brand_raw.lower()
                brand = lux.get(key) or next((v for k, v in lux.items() if key.startswith(k)), None)
                if not brand or not new: continue
                pid = m.group(1)
                im = re.search(r'(https://cdn\.vipavenue\.ru/products/[^/]+/' + pid + r'/small/compress/[^" ]+)', body)
                items.append(dict(id="v" + pid, src="VIP Avenue", b=brand, g=g, t=name or "Вещь", c=classify(name),
                                  p=new, o=old, s="/".join(sizes), k="new",
                                  u=f"https://www.vipavenue.ru/product/{pid}-{m.group(2)}/", i=im.group(1) if im else "", auth="shop"))
            log(f"vip {bname} {section} p{page}: карточек {got}, всего {len(items)}")
            if got < 40: break
    return items

def src_ozon(cfg):
    items = []
    for c in cfg["categories"]:
        body = fetch(c["url"])
        if not body: continue
        for t in re.split(r'<div data-index="\d+" class="tile-root', body)[1:]:
            t = t.split("<div data-index=")[0]
            m = re.search(r'href="(/product/[a-z0-9-]+-(\d+))/', t)
            if not m: continue
            text = txt(t)
            prices = [money(x) for x in re.findall(r"(\d[\d\s ]*)\s*₽", text)]
            prices = [x for x in prices if x and x > 300]
            if not prices: continue
            p = prices[0]; o = max(prices[1:]) if len(prices) > 1 and max(prices[1:]) > p else None
            img = (re.search(r'src="(https://ir[^"]+)"', t) or [None, ""])[1]
            after = text.split("₽")[-1]
            after = re.split(r"\s\d[.,]\d\s+\d+\s+отзыв|\s\d+\s+отзыв|\s(?:Завтра|Послезавтра|\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря))", after)[0]
            after = re.sub(r"−\d+%|\d+ ед осталось|Осталось мало|Распродажа|Цена что надо|Оригинал", "", after).strip()
            name = re.sub(r"^(?:" + re.escape(c["brand"]) + r"\s+)+", "", after, flags=re.I).strip()[:90]
            items.append(dict(id="z" + m.group(2), src="Ozon", b=c["brand"], g=c["g"], t=name or "Вещь", c=classify(name, c.get("cat")),
                              p=p, o=o, s="", k="new", u="https://www.ozon.ru" + m.group(1) + "/", i=img, auth=False))
        log(f"ozon {c['url']}: всего {len(items)}")
    return items

# ---------------- scoring ----------------
def norm_type(it):
    t = it["t"].lower()
    for w in ["клатч", "тоут", "через плечо", "на плечо", "коротк", "поясн", "дорожн", "рюкзак", "мини","пуховик", "куртк", "пальто", "тренч", "кроссовк", "кеды", "лофер", "туфл", "ботин", "сапог", "сумк", "клатч", "рюкзак", "кошел", "ремень", "джемпер", "свитер", "кардиган", "брюк", "джинс", "футболк", "худи", "рубашк", "плать", "юбк", "пиджак", "костюм", "жилет"]:
        if w in t: return w
    return "?"

def score(items):
    grp = defaultdict(list); grp2 = defaultdict(list)
    for it in items:
        if it["src"] == "Ozon": continue  # реплики не участвуют в медиане оригиналов
        grp[(it["b"], norm_type(it), it["k"])].append(it["p"])
        if it.get("mdl"): grp[(it["b"], "m:" + it["mdl"], "any")].append(it["p"])
        grp2[(it["b"], it["c"], it["k"])].append(it["p"])
    for it in items:
        a = grp.get((it["b"], "m:" + it["mdl"], "any"), []) if it.get("mdl") else []
        if len(a) < 4: a = grp.get((it["b"], norm_type(it), it["k"]), [])
        if norm_type(it) == "?": a = []
        if len(a) >= 4:
            m = statistics.median(a); it["m"] = int(round(m, -2)); it["v"] = round((1 - it["p"] / m) * 100)
        off = round((1 - it["p"] / it["o"]) * 100) if it.get("o") and it["o"] > it["p"] else 0
        if not off: it["o"] = None
        it["off"] = off
        # подозрения
        flags = []
        if it["src"] == "Ozon":
            flags.append("Почти наверняка реплика: оригиналы этого бренда на маркетплейсе так не стоят")
        elif it.get("v") is not None and it["v"] >= 70:
            flags.append("Цена ниже рынка больше чем на 70%: проверь подлинность и состояние")
        elif off >= 85 and it["k"] == "used":
            flags.append("Скидка больше 85% от исходной цены продавца: уточни, откуда вещь")
        if flags: it["f"] = flags
        if it["src"] == "Ozon":
            it.pop("v", None); it.pop("m", None)
            it["x"] = round(max(off, 0) * 0.3)
        else:
            it["x"] = round(max(off, 0) * 0.55 + max(min(it.get("v") or 0, 90), 0) * 0.45)
        if it["c"] in ("outer", "clothes"): it["L"] = letters(it["s"], it["g"])
        if it["c"] in ("shoes", "sneakers"): it["E"] = shoes(it["s"])
    return items

def main(cfg_path, out_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    jobs = {"oskelly": src_oskelly, "cultt": src_cultt, "vip": src_vip, "ozon": src_ozon}
    allit = []
    with ThreadPoolExecutor(4) as ex:
        futs = {ex.submit(fn, cfg[k]): k for k, fn in jobs.items() if k in cfg}
        for f, k in futs.items():
            try: res = f.result(); log(f"== {k}: {len(res)}"); allit += res
            except Exception as e: log(f"== {k} упал: {e}")
    uniq = {}
    for it in allit: uniq.setdefault(it["id"], it)
    items = score(list(uniq.values()))
    keep_min = cfg.get("keep_min_score", 20)
    deals = [it for it in items if it["x"] >= keep_min or it.get("f")]
    deals.sort(key=lambda it: -it["x"])
    stats = defaultdict(int)
    for it in items: stats[it["src"]] += 1
    out = {"updatedAt": time.strftime("%Y-%m-%d"), "scanned": len(items), "bySource": stats, "items": deals}
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    log(f"просмотрено {len(items)}, выгодных {len(deals)}; по источникам {dict(stats)}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
