# core/areas.py
# アプリ内で使う「主要エリア」定義（必要に応じて編集/追加OK）

AREAS = [
    # slug は英数小文字&ハイフン。lat/lng は中心座標の目安（±数百mでOK）
    {"slug": "shinjuku-west", "name": "新宿西口", "lat": 35.690, "lng": 139.699},
    {"slug": "shinjuku-sanchome", "name": "新宿三丁目", "lat": 35.690, "lng": 139.705},
    {"slug": "shibuya-center", "name": "渋谷センター街", "lat": 35.659, "lng": 139.700},
    {"slug": "ebisu", "name": "恵比寿駅周辺", "lat": 35.646, "lng": 139.709},
    {"slug": "nakame", "name": "中目黒駅周辺", "lat": 35.643, "lng": 139.699},
    {"slug": "ikebukuro-east", "name": "池袋東口", "lat": 35.731, "lng": 139.715},
    {"slug": "ueno", "name": "上野駅周辺", "lat": 35.713, "lng": 139.776},
    {"slug": "akihabara", "name": "秋葉原駅周辺", "lat": 35.698, "lng": 139.773},
    {"slug": "ginza", "name": "銀座四丁目", "lat": 35.671, "lng": 139.765},
    {"slug": "kichijoji", "name": "吉祥寺駅周辺", "lat": 35.704, "lng": 139.579},
    {"slug": "oomachi", "name": "大井町駅周辺", "lat": 35.605, "lng": 139.734},
    {"slug": "kawasaki", "name": "川崎駅東口", "lat": 35.531, "lng": 139.701},
]

AREAS_BY_SLUG = {a["slug"]: a for a in AREAS}

def area_choices():
    # フォーム用の (slug, name)
    return [(a["slug"], a["name"]) for a in AREAS]

def get_area(slug: str):
    return AREAS_BY_SLUG.get(slug)

def haversine_km(lat1, lng1, lat2, lng2):
    # 移動距離の概算（km）
    import math
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(rlat1)*math.cos(rlat2)*math.sin(dlng/2)**2
    return 2*R*math.asin(math.sqrt(a))

def distance_km_between(slug1: str, slug2: str) -> float:
    a1, a2 = get_area(slug1), get_area(slug2)
    if not a1 or not a2: return 0.0
    return haversine_km(a1["lat"], a1["lng"], a2["lat"], a2["lng"])
