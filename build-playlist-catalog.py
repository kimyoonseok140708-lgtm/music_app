import concurrent.futures
import html
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path


APPLE_PLAYLISTS = [
    ("rap-excited", "https://music.apple.com/kr/playlist/pl.u-vxy6JY4FWYApAVZ", ["excited"]),
    ("rap-calm-dawn", "https://music.apple.com/kr/playlist/r/pl.u-PDb4YYgueK9E9lp", ["calm", "dawn"]),
    ("ballad-rap-blue-dawn", "https://music.apple.com/kr/playlist/pl.u-6mo4z8mf8AGDGyX", ["blue", "dawn"]),
    ("ballad-rap-blue-dawn-love", "https://music.apple.com/kr/playlist/n/pl.u-BNA6zqjuevmNmWD", ["blue", "dawn", "love"]),
    ("workout", "https://music.apple.com/kr/playlist/pl.u-vxy6JVMtWYApAVZ", ["workout"]),
    ("indie-calm-dawn-blue", "https://music.apple.com/kr/playlist/pl.u-AkAmvb3Cxm4Z41q", ["calm", "dawn", "blue"]),
    ("band-calm-dawn-blue", "https://music.apple.com/kr/playlist/b/pl.u-RRbV9eWsmPvav5Y", ["calm", "dawn", "blue"]),
    ("ballad-rap-love-dawn-blue", "https://music.apple.com/kr/playlist/3-mc%EB%AA%BD/pl.u-LdbqE75I2be1eXv", ["love", "dawn", "blue"]),
    ("ballad-calm-dawn-blue-love", "https://music.apple.com/kr/playlist/pl.u-leylMqlFM2kDkXr", ["calm", "dawn", "blue", "love"]),
    ("study", "https://music.apple.com/kr/playlist/2023-2/pl.u-Ldbqe0rt2be1eXv", ["study"]),
]

SOUNDCLOUD_URL = (
    "https://soundcloud.com/kckjpt0gwdhf/sets/jz79tzpiw9av"
    "?si=6775a3848105440792912d1ff5bdcdf1&utm_source=clipboard"
    "&utm_medium=text&utm_campaign=social_sharing"
)

MOODS = ["excited", "calm", "dawn", "blue", "workout", "love", "study"]


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/130 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8")


def parse_apple_playlist(playlist):
    key, url, moods = playlist
    source = fetch(url)
    playlist_id = re.search(r"pl\.u-[A-Za-z0-9]+", url)
    if not playlist_id:
        raise RuntimeError(f"Could not identify playlist ID: {url}")
    prefix = r'\{"id":"track-lockup - ' + re.escape(playlist_id.group(0)) + r' - \d+"'
    starts = list(re.finditer(prefix, source))
    rows = []
    for match in starts:
        row, _ = json.JSONDecoder().raw_decode(source, match.start())
        descriptor = row.get("contentDescriptor", {})
        track_id = descriptor.get("identifiers", {}).get("storeAdamID")
        title = row.get("title", "").strip()
        artist = row.get("artistName", "").strip()
        if track_id and title and artist:
            rows.append(
                {
                    "id": "apple-" + str(track_id),
                    "title": title,
                    "artist": artist,
                    "moods": list(moods),
                    "source": key,
                    "appleUrl": descriptor.get("url", ""),
                }
            )

    count_match = re.search(r'<meta property="music:song_count" content="(\d+)"', source)
    expected = int(count_match.group(1)) if count_match else None
    if not rows:
        raise RuntimeError(f"No songs could be read from {url}")
    if expected is not None and len(rows) != expected:
        raise RuntimeError(
            f"{key}: parsed {len(rows)} of {expected} published playlist songs."
        )
    return key, rows, expected


def parse_soundcloud():
    source = fetch(SOUNDCLOUD_URL)
    match = re.search(r"window\.__sc_hydration\s*=\s*(\[.*?\])\s*;", source, re.S)
    if not match:
        raise RuntimeError("Could not read the shared SoundCloud playlist data.")
    data = json.loads(match.group(1))
    playlist = next(
        (item.get("data") for item in data if item.get("hydratable") == "playlist"),
        None,
    )
    if not playlist:
        raise RuntimeError("SoundCloud did not expose playlist metadata.")
    songs = []
    for track in playlist.get("tracks", []):
        title = (track.get("title") or "").strip()
        artist = (track.get("user") or {}).get("username", "").strip()
        if not title or not artist:
            continue
        songs.append(
            {
                "id": "soundcloud-" + str(track.get("id", "")),
                "title": title,
                "artist": artist,
                "moods": ["excited"],
                "source": "soundcloud",
                "appleUrl": "",
            }
        )
    return playlist.get("title", ""), songs, playlist.get("track_count")


def parse_melon_top100():
    source = fetch("https://www.melon.com/chart/index.htm")
    rows = []
    cursor = 0
    while True:
        start = source.find('<tr class="lst', cursor)
        if start < 0:
            break
        end = source.find("</tr>", start)
        if end < 0:
            break
        block = source[start:end]

        def between(text, opening, closing, offset=0):
            found = text.find(opening, offset)
            if found < 0:
                return ""
            found += len(opening)
            stop = text.find(closing, found)
            return text[found:stop] if stop >= 0 else ""

        song_id = between(block, 'data-song-no="', '"')
        rank_marker = block.find('<span class="rank')
        rank = between(block, ">", "<", rank_marker)
        title_div = block.find('<div class="ellipsis rank01">')
        artist_div = block.find('<div class="ellipsis rank02">')
        title_anchor = block.find("<a", title_div)
        artist_anchor = block.find("<a", artist_div)
        title = between(block, ">", "</a>", title_anchor)
        artist = between(block, ">", "</a>", artist_anchor)
        try:
            rank_number = int(rank.strip())
        except ValueError:
            rank_number = 0
        if song_id and title and artist and 1 <= rank_number <= 100:
            rows.append(
                {
                    "id": "melon-" + song_id,
                    "title": html.unescape(title).strip(),
                    "artist": html.unescape(artist).replace("\xa0", " ").strip(),
                    "rank": rank_number,
                }
            )
        cursor = end + len("</tr>")

    by_rank = {row["rank"]: row for row in rows}
    if len(by_rank) != 100:
        raise RuntimeError(f"Melon returned {len(by_rank)} unique ranks, not 100.")
    return [by_rank[rank] for rank in range(1, 101)]


def normalize(value):
    return re.sub(r"[^\w]", "", value.casefold())


def infer_chart_moods(song):
    title = song["title"].casefold()
    artist = song["artist"].casefold()
    result = []
    if any(word in title for word in ["눈물", "이별", "한숨", "헤어", "그리워", "후회", "sad", "goodbye", "tears"]):
        result.append("blue")
    if any(word in title for word in ["밤", "새벽", "별", "달빛", "night", "moon", "midnight"]):
        result.append("dawn")
    if any(word in title for word in ["사랑", "고백", "좋아", "너를", "love", "kiss", "heart"]):
        result.append("love")
    if any(word in title for word in ["piano", "피아노", "연주곡", "instrumental"]):
        result.append("study")

    ballad_artists = [
        "iu", "아이유", "taeyeon", "태연", "heize", "헤이즈", "paul kim", "폴킴",
        "sung si kyung", "성시경", "meloMance".casefold(), "멜로망스", "lee mujin",
        "이무진", "hynn", "박혜원", "kassy", "케이시", "10cm", "정승환", "이하이",
        "이영현", "린", "다비치", "임영웅", "볼빨간사춘기", "악뮤", "akmu",
    ]
    energetic_artists = [
        "bts", "방탄소년단", "ive", "아이브", "aespa", "에스파", "blackpink",
        "블랙핑크", "stray kids", "스트레이 키즈", "le sserafim", "뉴진스",
        "newjeans", "세븐틴", "seventeen", "ateez", "엔믹스", "nmixx", "itzy",
        "빅뱅", "bigbang", "nct", "아이들", "gidle", "트와이스", "twice",
        "정국", "jungkook", "psy", "싸이",
    ]
    rapper_artists = [
        "mc", "창모", "changmo", "지코", "zico", "제시", "jessi", "비오", "be'o",
        "에픽하이", "epik high", "다이나믹듀오", "dynamicduo", "이영지",
    ]
    if any(name in artist for name in ballad_artists):
        result.extend(["calm", "blue", "dawn"])
    elif any(name in artist for name in rapper_artists):
        result.extend(["excited", "workout"])
    elif any(name in artist for name in energetic_artists):
        result.extend(["excited", "workout"])
    else:
        result.extend(["calm", "love"])
    return list(dict.fromkeys(result))


def main():
    apple_results = {}
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(parse_apple_playlist, item): item[0] for item in APPLE_PLAYLISTS}
        soundcloud_future = pool.submit(parse_soundcloud)
        melon_future = pool.submit(parse_melon_top100)
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                apple_results[key] = future.result()
            except Exception as error:
                errors.append(f"{key}: {error}")
        try:
            soundcloud_title, soundcloud_songs, soundcloud_count = soundcloud_future.result()
        except Exception as error:
            errors.append(f"SoundCloud: {error}")
            soundcloud_title, soundcloud_songs, soundcloud_count = "", [], None
        try:
            melon_rows = melon_future.result()
        except Exception as error:
            errors.append(f"Melon Top 100: {error}")
            melon_rows = []

    if errors:
        raise RuntimeError("Catalog is incomplete:\n" + "\n".join(errors))

    songs_by_id = {}
    identity_to_id = {}

    def add_song(song):
        identity = (normalize(song["artist"]), normalize(song["title"]))
        existing_id = identity_to_id.get(identity)
        if existing_id:
            existing = songs_by_id[existing_id]
            for mood in song["moods"]:
                if mood not in existing["moods"]:
                    existing["moods"].append(mood)
            if song.get("source") == "melon-top100":
                existing["melonRank"] = song["melonRank"]
            if not existing.get("appleUrl") and song.get("appleUrl"):
                existing["appleUrl"] = song["appleUrl"]
            return
        if song["id"] in songs_by_id:
            existing = songs_by_id[song["id"]]
            for mood in song["moods"]:
                if mood not in existing["moods"]:
                    existing["moods"].append(mood)
            return
        song["moods"] = [mood for mood in MOODS if mood in song["moods"]]
        song["mood"] = song["moods"][0] if song["moods"] else "calm"
        songs_by_id[song["id"]] = song
        identity_to_id[identity] = song["id"]

    for key, _, _ in APPLE_PLAYLISTS:
        _, tracks, expected = apple_results[key]
        print(f"Apple playlist {key}: {len(tracks)}/{expected}")
        for track in tracks:
            add_song(track)

    print(f"SoundCloud playlist {soundcloud_title!r}: {len(soundcloud_songs)}/{soundcloud_count}")
    for track in soundcloud_songs:
        add_song(track)

    for row in melon_rows:
        track = {
            "id": row["id"],
            "title": row["title"],
            "artist": row["artist"],
            "moods": infer_chart_moods(row),
            "source": "melon-top100",
            "melonRank": row["rank"],
            "appleUrl": "",
        }
        add_song(track)

    songs = list(songs_by_id.values())
    if not all(song["moods"] for song in songs):
        raise RuntimeError("Some songs were left without a mood.")
    catalog = "window.MOODIE_SONGS = " + json.dumps(
        songs, ensure_ascii=True, separators=(",", ":")
    ) + ";\n"
    Path("songs-catalog.js").write_text(catalog, encoding="ascii")

    print(f"Catalog: {len(songs)} unique songs, Melon Top 100 parsed.")
    print("Mood counts:", dict(Counter(mood for song in songs for mood in song["moods"])))


if __name__ == "__main__":
    main()
