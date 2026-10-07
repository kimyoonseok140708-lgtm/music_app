const moods = [
  { id: "excited", label: "신나는", emoji: "🔥", color: "#ffeadb" },
  { id: "calm", label: "편안한", emoji: "😌", color: "#e6f0e6" },
  { id: "dawn", label: "새벽 감성", emoji: "🌙", color: "#e9e6f5" },
  { id: "blue", label: "우울한", emoji: "😢", color: "#e4edf6" },
  { id: "workout", label: "운동할 때", emoji: "💪", color: "#f8e6db" },
  { id: "love", label: "사랑/설렘", emoji: "❤️", color: "#f9e3e5" },
  { id: "study", label: "공부할 때", emoji: "📚", color: "#f3edda" },
];

const songs = window.MOODIE_SONGS;

const STORAGE_KEYS = {
  liked: "moodie-liked-songs-v3",
  recent: "moodie-recent-songs-v3",
};
const artColors = [
  ["#f7cbb5", "#e89072"],
  ["#d3e4d5", "#83b59b"],
  ["#c9c4e7", "#8581b6"],
  ["#c4dce9", "#7babc2"],
  ["#f2d3a5", "#e5a66e"],
  ["#f3c5cb", "#df8894"],
  ["#ede1b8", "#c6ab68"],
];

let currentSong = null;
let currentMood = null;
let likedSongs = keepCatalogSongs(readStorage(STORAGE_KEYS.liked));
let recentSongs = keepCatalogSongs(readStorage(STORAGE_KEYS.recent));

const moodGrid = document.querySelector("#mood-grid");
const resultDialog = document.querySelector("#result-dialog");
const flipCard = document.querySelector("#flip-card");
const otherPlatforms = [
  { label: "YouTube", url: (term) => `https://www.youtube.com/results?search_query=${encodeURIComponent(term)}` },
  { label: "Spotify", url: (term) => `https://open.spotify.com/search/${encodeURIComponent(term)}` },
  { label: "Melon", url: (term) => `https://www.melon.com/search/song/index.htm?q=${encodeURIComponent(term)}` },
  { label: "Genie Music", url: (term) => `https://www.genie.co.kr/search/searchMain?query=${encodeURIComponent(term)}` },
  { label: "SoundCloud", url: (term) => `https://soundcloud.com/search/sounds?q=${encodeURIComponent(term)}` },
];

function readStorage(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (error) {
    console.warn(`저장된 데이터를 읽지 못했습니다 (${key}).`, error);
    return [];
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.error(`데이터를 저장하지 못했습니다 (${key}).`, error);
    return false;
  }
}

function keepCatalogSongs(savedSongs) {
  const catalog = new Map(songs.map((song) => [song.id, song]));
  return savedSongs.filter((song) => catalog.has(song?.id)).map((song) => catalog.get(song.id));
}

function moodFor(id) {
  return moods.find((mood) => mood.id === id);
}

function renderMoods() {
  moodGrid.replaceChildren();
  moods.forEach((mood) => {
    const button = document.createElement("button");
    button.className = "mood-button";
    button.type = "button";
    button.setAttribute("aria-label", `${mood.label} 음악 추천 보기`);
    button.innerHTML = `
      <span class="mood-emoji" style="--mood-bg: ${mood.color}" aria-hidden="true">${mood.emoji}</span>
      <span class="mood-label">${mood.label}</span>
      <span class="mood-arrow" aria-hidden="true">›</span>
    `;
    button.addEventListener("click", () => {
      currentMood = mood.id;
      showSong(pickSong(mood.id));
    });
    moodGrid.append(button);
  });
}

function pickSong(moodId, excludeId = null) {
  const options = songs.filter(
    (song) => song.moods?.includes(moodId) && song.id !== excludeId,
  );
  const fallback = songs.filter((song) => song.moods?.includes(moodId));
  const candidates = options.length ? options : fallback;
  return candidates[Math.floor(Math.random() * candidates.length)];
}

function pickDailySong() {
  currentMood = null;
  const options = songs.filter((song) => song.id !== currentSong?.id);
  return options[Math.floor(Math.random() * options.length)];
}

function showSong(song) {
  if (!song) return;
  currentSong = song;
  const displayMoodId = currentMood && song.moods?.includes(currentMood)
    ? currentMood
    : song.moods?.[0] || song.mood;
  const mood = moodFor(displayMoodId);
  document.querySelector("#result-eyebrow").textContent = mood
    ? `${mood.emoji} ${mood.label} PLAYLIST`
    : "YOUR SONG";
  document.querySelector("#song-mood").textContent = mood ? `${mood.emoji} ${mood.label}` : "오늘의 랜덤 추천";
  document.querySelector("#result-title").textContent = song.title;
  document.querySelector("#result-artist").textContent = song.artist;

  const [colorA, colorB] = artColors[moods.findIndex((item) => item.id === displayMoodId)] || artColors[0];
  document.querySelector("#album-art").style.setProperty("--art-a", colorA);
  document.querySelector("#album-art").style.setProperty("--art-b", colorB);
  document.querySelector("#listen-song").href =
    `https://music.apple.com/kr/search?term=${encodeURIComponent(`${song.title} ${song.artist}`)}`;
  renderPlatformLinks(song);

  recentSongs = [song, ...recentSongs.filter((item) => item.id !== song.id)].slice(0, 8);
  writeStorage(STORAGE_KEYS.recent, recentSongs);
  updateLikeButton();
  renderLibrary();

  flipCard.style.animation = "none";
  void flipCard.offsetWidth;
  flipCard.style.animation = "";
  resultDialog.showModal();
}

function renderPlatformLinks(song) {
  const query = `${song.title} ${song.artist}`;
  const container = document.querySelector("#platform-links");
  container.replaceChildren();
  otherPlatforms.forEach((platform) => {
    const link = document.createElement("a");
    link.className = "platform-link";
    link.href = platform.url(query);
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = `${platform.label}에서 듣기`;
    container.append(link);
  });
}

function updateLikeButton() {
  const isLiked = likedSongs.some((song) => song.id === currentSong?.id);
  const button = document.querySelector("#like-song");
  button.classList.toggle("is-liked", isLiked);
  button.textContent = isLiked ? "♥ 좋아요 완료" : "♡ 좋아요";
  button.setAttribute("aria-pressed", String(isLiked));
}

function renderSavedSongs(containerId, list, emptyMessage) {
  const container = document.querySelector(containerId);
  container.replaceChildren();
  if (!list.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyMessage;
    container.append(empty);
    return;
  }

  list.forEach((song) => {
    const row = document.createElement("div");
    row.className = "saved-song";
    const art = document.createElement("span");
    art.className = "saved-song-art";
    art.textContent = "♫";
    const details = document.createElement("div");
    details.style.minWidth = "0";
    const title = document.createElement("div");
    title.className = "saved-song-title";
    title.textContent = song.title;
    const artist = document.createElement("div");
    artist.className = "saved-song-artist";
    artist.textContent = song.artist;
    details.append(title, artist);
    row.append(art, details);
    container.append(row);
  });
}

function renderLibrary() {
  renderSavedSongs("#liked-list", likedSongs, "아직 좋아요한 노래가 없어요.");
  renderSavedSongs("#recent-list", recentSongs, "추천받은 노래가 여기에 저장돼요.");
}

function closeResult() {
  resultDialog.close();
}

renderMoods();
renderLibrary();

document.querySelector("#draw-song").addEventListener("click", () => showSong(pickDailySong()));
document.querySelector("#redraw-song").addEventListener("click", () => {
  const nextSong = currentMood
    ? pickSong(currentMood, currentSong?.id)
    : pickDailySong();
  showSong(nextSong);
});
document.querySelector("#like-song").addEventListener("click", () => {
  if (!currentSong) return;
  const isLiked = likedSongs.some((song) => song.id === currentSong.id);
  likedSongs = isLiked
    ? likedSongs.filter((song) => song.id !== currentSong.id)
    : [currentSong, ...likedSongs];
  if (writeStorage(STORAGE_KEYS.liked, likedSongs)) {
    updateLikeButton();
    renderLibrary();
  }
});
document.querySelector("#close-result").addEventListener("click", closeResult);
resultDialog.addEventListener("click", (event) => {
  if (event.target === resultDialog) closeResult();
});
document.querySelector("#show-library").addEventListener("click", () => {
  const section = document.querySelector("#library-section");
  section.hidden = !section.hidden;
  if (!section.hidden) section.scrollIntoView({ behavior: "smooth", block: "center" });
});
document.querySelector("#close-library").addEventListener("click", () => {
  document.querySelector("#library-section").hidden = true;
});
