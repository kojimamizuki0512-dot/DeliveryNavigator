# core/areas.py

AREAS = [
    {"slug": "shibuya",   "name": "渋谷駅周辺",     "lat": 35.6595, "lng": 139.7005},
    {"slug": "ebisu",     "name": "恵比寿駅周辺",   "lat": 35.6467, "lng": 139.7101},
    {"slug": "shinjuku",  "name": "新宿駅周辺",     "lat": 35.6900, "lng": 139.7000},
    {"slug": "ikebukuro", "name": "池袋駅周辺",     "lat": 35.7295, "lng": 139.7100},
    {"slug": "ueno",      "name": "上野駅周辺",     "lat": 35.7138, "lng": 139.7773},
    {"slug": "asakusa",   "name": "浅草・吾妻橋",   "lat": 35.7119, "lng": 139.7967},
    {"slug": "kanda",     "name": "神田・秋葉原",   "lat": 35.6917, "lng": 139.7708},
    {"slug": "ginza",     "name": "銀座・有楽町",   "lat": 35.6717, "lng": 139.7650},
]

AREA_INDEX = {a["slug"]: a for a in AREAS}
