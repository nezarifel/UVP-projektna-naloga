import requests
import re
import html
import csv
import time
import os

# Brickset caps browsing pagination at 500 results per query, regardless of
# sort order. To get all ~1090 sets from 2025 we split the query by theme
# (each theme has well under 500 sets) and page through each one.
THEMES = [
    "Animal-Crossing", "Architecture", "Art", "Bluey", "Books", "Botanicals",
    "BrickHeadz", "BrickLink", "City", "Classic", "Collectable-Minifigures",
    "Creator", "DC-Comics-Super-Heroes", "Disney", "Dreamzzz", "Duplo",
    "Education", "Fortnite", "Friends", "Gabby-s-Dollhouse", "Gear",
    "Harry-Potter", "Horizon", "Icons", "Ideas", "Jurassic-World",
    "Marvel-Super-Heroes", "Minecraft", "Miscellaneous", "Monkie-Kid",
    "Nike", "Ninjago", "One-Piece", "Powered-Up", "Promotional", "Seasonal",
    "Sonic-the-Hedgehog", "Speed-Champions", "Star-Wars", "Super-Mario",
    "Technic", "Wednesday", "Wicked",
]

FIELDNAMES = [
    "ime", "stevilka", "tema", "kosi", "ocena", "stevilo_ocen",
    "stevilo_recenzij", "velikost_modela", "navodila", "datum_izida",
]


def extract_data(block):
    data = {}

    # ime seta - obicajno <h1><a><span>10366: </span> Tropical Aquarium</a></h1>
    # pri knjigah (ISBN...) in nekaterih Bricklink setih je <span> prazen ali
    # vsebuje crke, zato imena ne iscemo vec preko stevilke v span-u
    ime_m = re.search(r"<div class='meta'><h1><a[^>]*>(.*?)</a></h1>", block, re.S)
    data["ime"] = None
    if ime_m:
        notranjost = re.sub(r"^<span>.*?</span>\s*", "", ime_m.group(1), flags=re.S)
        data["ime"] = html.unescape(notranjost.strip())

    # stevilka seta - obicajno samo stevilke (10366-1), pri knjigah pa npr.
    # ISBN9798217126040-1, pri nekaterih Bricklink setih pa L0002198-1
    stevilka = re.search(r"/sets/([A-Za-z0-9]+-\d+)/", block)
    data["stevilka"] = stevilka.group(1) if stevilka else None

    # lego tema, npr. Icons, City, Star-Wars ...
    tema = re.search(r"<a href='/sets/theme-[^']+'>([^<]+)</a>", block)
    data["tema"] = html.unescape(tema.group(1)) if tema else None

    # stevilo kosov
    kosi = re.search(r"Pieces</dt>\s*<dd>(?:<a[^>]*>)?\s*(\d[\d,]*)", block, re.I)
    data["kosi"] = kosi.group(1).replace(",", "") if kosi else None

    # ocena (zvezdice), npr. 4.8
    ocena = re.search(r"<div class='rating'>.*?\s([\d.]+)</span>", block, re.S)
    data["ocena"] = ocena.group(1) if ocena else None

    # stevilo ocen
    stevilo_ocen = re.search(r"(\d+)\s*ratings?", block)
    data["stevilo_ocen"] = stevilo_ocen.group(1) if stevilo_ocen else "0"

    # stevilo recenzij (reviews)
    stevilo_recenzij = re.search(r"(\d+)&nbsp;reviews?", block)
    data["stevilo_recenzij"] = stevilo_recenzij.group(1) if stevilo_recenzij else "0"

    # velikost modela, npr. "52 x 36 x 28 cm"
    velikost = re.search(r"Model size</dt>\s*<dd>(.*?)</dd>", block, re.S)
    data["velikost_modela"] = html.unescape(velikost.group(1).strip()) if velikost else None

    # ali obstajajo navodila (Yes/No)
    navodila = re.search(r"Instructions</dt>\s*<dd>.*?>Yes<", block, re.S)
    data["navodila"] = "Yes" if navodila else "No"

    # datum izida (launch date)
    datum = re.search(r"Launch/exit</dt>\s*<dd>(.*?)\s*-", block, re.S)
    data["datum_izida"] = html.unescape(datum.group(1).strip()) if datum else None

    return data


def get_page(session, url):
    """Fetch a URL, retrying with backoff if Cloudflare rate-limits us (429)."""
    response = None
    for poskus in range(6):
        response = session.get(url)
        if response.status_code == 429:
            cakaj = 15 * (poskus + 1)
            print(f"  429 -> čakam {cakaj}s in poskusim znova ({poskus + 1}/6)")
            time.sleep(cakaj)
            continue
        return response
    return response


all_data = []
seen_numbers = set()  # varovalka pred podvojenimi seti

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

for theme in THEMES:
    page = 1
    while True:
        if page == 1:
            url = f"https://brickset.com/sets/year-2025/theme-{theme}"
        else:
            url = f"https://brickset.com/sets/year-2025/theme-{theme}/page-{page}"

        print(f"Obdelujem: {url}")
        response = get_page(session, url)
        html_text = response.text

        blocks = re.findall(
            r"<article[^>]*class=[\"']set[\"'][^>]*>(.*?)</article>",
            html_text,
            re.S | re.I,
        )

        print(f"  Status: {response.status_code}  Najdenih blokov: {len(blocks)}")

        if len(blocks) == 0:
            break

        for block in blocks:
            data = extract_data(block)
            if data["stevilka"] and data["stevilka"] in seen_numbers:
                continue
            if data["stevilka"]:
                seen_numbers.add(data["stevilka"])
            all_data.append(data)

        page += 1
        time.sleep(5)

print("Skupaj setov:", len(all_data))

if all_data:
    izhodna_pot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lego_sets_all.csv")
    with open(izhodna_pot, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_data)

    print(f"Zapisano v: {izhodna_pot}")