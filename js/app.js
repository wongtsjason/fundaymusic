/* Stepped open-day wizard. Later answers stay when an earlier choice changes. */

const STORAGE_KEY = "woshi-xiege-workshop";

const GENRE_EN = {
  cantopop: "Cantopop",
  kpop: "K-pop",
  folk: "folk",
  ballad: "ballad",
  lightpop: "upbeat pop",
  rock: "rock",
};

const GENRE_ZH = {
  cantopop: "粵語流行",
  kpop: "K-Pop",
  folk: "民謠",
  ballad: "抒情",
  lightpop: "輕快流行",
  rock: "搖滾",
};

const INSTRUMENTS = [
  ["acoustic", "acoustic guitar"],
  ["electric", "electric guitar"],
  ["piano", "piano"],
  ["violin", "violin"],
  ["synth", "synthesizer"],
  ["drums", "drum kit"],
  ["harmonica", "harmonica"],
];

const INSTRUMENT_ZH = {
  acoustic: "木結他",
  electric: "電結他",
  piano: "鋼琴",
  violin: "小提琴",
  synth: "合成器",
  drums: "爵士鼓",
  harmonica: "口琴",
};

const TEMPO_EN = {
  slow: "slow tempo 72 BPM",
  mid: "mid-tempo 100 BPM",
  fast: "fast tempo 128 BPM",
};

const MOOD_EN = {
  warm: "warm",
  grateful: "grateful",
  happy: "cheerful",
  moved: "touching",
  lively: "energetic",
};

const LANG_EN = {
  yue: "Cantonese vocals",
  cmn: "Mandarin vocals",
};

const STEP_NAMES = ["歌種", "樂器", "速度", "氛圍", "語言", "歌詞", "結果"];

const steps = [...document.querySelectorAll(".step")];
const stepperItems = [...document.querySelectorAll(".stepper-item")];
const lyricsInput = document.getElementById("lyrics");
const lineCount = document.getElementById("line-count");
const lyricsReady = document.getElementById("lyrics-ready");
const instrumentCount = document.getElementById("instrument-count");
const styleOut = document.getElementById("style-out");
const lyricsOut = document.getElementById("lyrics-out");
const progressBar = document.getElementById("progress-bar");
const progress = document.getElementById("progress");
const progressCount = document.getElementById("progress-count");
const live = document.getElementById("live");
const resetBtn = document.getElementById("reset");

const audioMap = {};
document.querySelectorAll("audio[data-id]").forEach((audio) => {
  audioMap[audio.dataset.id] = audio;
});

let playingId = null;
let playToken = 0;
let seenReveal = 0;
let booted = false;
let lastStepperIndex = -1;
let latestStyle = "";
let latestLyrics = "";
const copyTimers = new Map();
let resetArmed = false;
let resetTimer = 0;

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function announce(message) {
  live.textContent = "";
  window.setTimeout(() => {
    live.textContent = message;
  }, 30);
}

function readState() {
  const checked = (name) =>
    document.querySelector(`input[name="${name}"]:checked`)?.value || "";
  return {
    genre: checked("genre"),
    instruments: [...document.querySelectorAll('input[name="instrument"]:checked')].map(
      (el) => el.value
    ),
    tempo: checked("tempo"),
    mood: checked("mood"),
    language: checked("language"),
    lyrics: lyricsInput.value,
  };
}

function validityOf(state) {
  return [
    Boolean(state.genre),
    state.instruments.length > 0,
    Boolean(state.tempo),
    Boolean(state.mood),
    Boolean(state.language),
    state.lyrics.trim().length > 0,
  ];
}

function currentIndex(flags) {
  const missing = flags.findIndex((ok) => !ok);
  return missing === -1 ? 6 : missing;
}

function buildStyle(state) {
  const instruments = INSTRUMENTS.filter(([id]) => state.instruments.includes(id)).map(
    ([, en]) => en
  );
  return [
    GENRE_EN[state.genre],
    ...instruments,
    TEMPO_EN[state.tempo],
    MOOD_EN[state.mood],
    LANG_EN[state.language],
  ].join(", ");
}

function buildLyrics(raw) {
  const text = raw.replace(/\r\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  if (!text) return "";
  if (/^\s*\[[A-Za-z][^\]]*\]/.test(text)) return text;
  return `[Verse]\n${text}`;
}

function lyricLineCount(text) {
  return text
    .split(/\n/)
    .map((line) => line.trim())
    .filter(Boolean).length;
}

function lineCountMessage(count) {
  if (count <= 0) return "建議寫 3 至 4 行，一句一行。";
  if (count < 3) return `已寫 ${count} 行。可以再寫一兩句。`;
  if (count <= 4) return `已寫 ${count} 行。可以到下面的結果。`;
  return `已寫 ${count} 行。3 至 4 行就很夠。`;
}

function paintSelections() {
  document.querySelectorAll(".choice, .chip, .tile").forEach((el) => {
    const input = el.querySelector("input");
    el.classList.toggle("is-selected", Boolean(input && input.checked));
  });
  document.querySelectorAll(".choice").forEach((row) => {
    const id = row.querySelector(".play-btn")?.dataset.audio;
    row.classList.toggle("is-playing", id === playingId);
  });
}

function paintAudioButtons() {
  document.querySelectorAll(".play-btn").forEach((button) => {
    const on = button.dataset.audio === playingId;
    const name = GENRE_ZH[button.dataset.audio] || "預覽";
    button.setAttribute("aria-pressed", on ? "true" : "false");
    button.setAttribute("aria-label", on ? `停止播放${name}` : `試聽${name}，約 8 秒`);
  });
  paintSelections();
}

function paintInstrumentSummary(state) {
  if (!state.instruments.length) {
    instrumentCount.textContent = "尚未選擇。";
    return;
  }
  const names = state.instruments.map((id) => INSTRUMENT_ZH[id] || id);
  instrumentCount.textContent = `已選：${names.join("、")}`;
}

function updateResult(state, flags) {
  const ready = flags.every(Boolean);
  lyricsReady.hidden = !flags[5];
  if (!ready) {
    latestStyle = "";
    latestLyrics = "";
    styleOut.textContent = "";
    lyricsOut.textContent = "";
    return;
  }
  latestStyle = buildStyle(state);
  latestLyrics = buildLyrics(state.lyrics);
  styleOut.textContent = latestStyle;
  lyricsOut.textContent = latestLyrics;
}

function updateStepper(current) {
  const done = Math.min(current, 6);
  progressCount.textContent = `${done}／6`;
  progressBar.style.width = `${(done / 6) * 100}%`;
  progress.setAttribute("aria-valuenow", String(done));
  stepperItems.forEach((item, index) => {
    const isCurrent = index === current;
    item.classList.toggle("is-current", isCurrent);
    item.classList.toggle("is-done", index < current);
    item.disabled = index > current;
    if (isCurrent) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
  const currentItem = stepperItems[current];
  if (currentItem && booted && current !== lastStepperIndex) {
    const row = currentItem.parentElement;
    const left = currentItem.offsetLeft - (row.clientWidth - currentItem.clientWidth) / 2;
    row.scrollTo({ left: Math.max(0, left), behavior: reduceMotion ? "auto" : "smooth" });
  }
  lastStepperIndex = current;
}

function update(options = {}) {
  const state = readState();
  const flags = validityOf(state);
  const current = currentIndex(flags);
  const revealCount = current + 1;

  steps.forEach((step, index) => {
    step.hidden = index > current;
    step.classList.toggle("is-current", index === current);
    step.classList.toggle("is-done", index < current);
  });

  paintSelections();
  paintInstrumentSummary(state);
  lineCount.textContent = lineCountMessage(lyricLineCount(state.lyrics));
  updateResult(state, flags);
  updateStepper(current);

  if (!booted) {
    seenReveal = revealCount;
  } else if (revealCount > seenReveal) {
    const typing = document.activeElement === lyricsInput;
    if (!typing) {
      steps[current].scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "start",
      });
    }
    announce(`下一步：${STEP_NAMES[current]}`);
    seenReveal = revealCount;
  } else {
    seenReveal = revealCount;
  }

  if (options.save !== false) save(state);
}

function save(state) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    /* Private mode can refuse storage. The wizard still works. */
  }
}

function restore() {
  let data = null;
  try {
    data = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
  } catch (err) {
    data = null;
  }
  if (!data || typeof data !== "object") return;

  const check = (name, value) => {
    const input = [...document.querySelectorAll(`input[name="${name}"]`)].find(
      (el) => el.value === value
    );
    if (input) input.checked = true;
  };

  if (typeof data.genre === "string") check("genre", data.genre);
  if (Array.isArray(data.instruments)) {
    data.instruments.forEach((value) => {
      if (typeof value === "string") check("instrument", value);
    });
  }
  if (typeof data.tempo === "string") check("tempo", data.tempo);
  if (typeof data.mood === "string") check("mood", data.mood);
  if (typeof data.language === "string") check("language", data.language);
  if (typeof data.lyrics === "string") lyricsInput.value = data.lyrics;
}

function haltAudio() {
  playToken += 1;
  Object.values(audioMap).forEach((audio) => {
    audio.pause();
    audio.currentTime = 0;
  });
  playingId = null;
  paintAudioButtons();
}

function togglePreview(id) {
  const audio = audioMap[id];
  if (!audio) return;
  if (playingId === id) {
    haltAudio();
    announce("已停止播放");
    return;
  }
  haltAudio();
  const name = GENRE_ZH[id] || "預覽";
  try {
    audio.currentTime = 0;
  } catch (err) {
    /* If the file is missing, play() reports it below. */
  }
  playingId = id;
  paintAudioButtons();
  const token = playToken;
  let pending;
  try {
    pending = audio.play();
  } catch (err) {
    playingId = null;
    paintAudioButtons();
    announce("這段示範暫時未能播放");
    return;
  }
  announce(`正在播放${name}`);
  if (pending && typeof pending.catch === "function") {
    pending.catch(() => {
      if (playToken !== token) return;
      playingId = null;
      paintAudioButtons();
      announce("這段示範暫時未能播放");
    });
  }
}

function selectElementText(el) {
  const range = document.createRange();
  range.selectNodeContents(el);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = text;
  helper.setAttribute("readonly", "");
  helper.style.position = "fixed";
  helper.style.top = "0";
  helper.style.left = "0";
  helper.style.opacity = "0";
  document.body.appendChild(helper);
  helper.focus();
  helper.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(helper);
  if (!ok) throw new Error("copy failed");
}

function showCopied(button) {
  const label = button.dataset.label || "複製";
  button.textContent = "已複製";
  button.classList.add("is-copied");
  window.clearTimeout(copyTimers.get(button));
  copyTimers.set(
    button,
    window.setTimeout(() => {
      button.textContent = label;
      button.classList.remove("is-copied");
    }, 1600)
  );
}

async function onCopy(button) {
  const target = document.getElementById(button.dataset.target);
  const text = button.dataset.target === "style-out" ? latestStyle : latestLyrics;
  if (!text) return;
  try {
    await copyText(text);
    showCopied(button);
    announce(`已複製：${button.dataset.announce || "內容"}`);
  } catch (err) {
    selectElementText(target);
    announce("未能自動複製，請長按文字再複製");
  }
}

function resetAll() {
  haltAudio();
  document
    .querySelectorAll('input[type="radio"], input[type="checkbox"]')
    .forEach((input) => {
      input.checked = false;
    });
  lyricsInput.value = "";
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    /* Ignore. */
  }
  update({ save: false });
  window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
  announce("已清除，可以重新開始");
}

document.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((input) => {
  input.addEventListener("change", () => update());
});

lyricsInput.addEventListener("input", () => update());

document.querySelectorAll(".play-btn").forEach((button) => {
  button.addEventListener("click", () => togglePreview(button.dataset.audio));
});

document.querySelectorAll(".copy-btn").forEach((button) => {
  button.addEventListener("click", () => {
    onCopy(button);
  });
});

stepperItems.forEach((item) => {
  item.addEventListener("click", () => {
    if (item.disabled) return;
    const target = document.getElementById(item.dataset.target);
    if (!target || target.hidden) return;
    target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  });
});

Object.entries(audioMap).forEach(([id, audio]) => {
  const clearIfCurrent = () => {
    if (playingId !== id) return;
    playingId = null;
    paintAudioButtons();
  };
  audio.addEventListener("ended", clearIfCurrent);
  audio.addEventListener("timeupdate", () => {
    if (audio.currentTime >= 9.95) {
      audio.pause();
      audio.currentTime = 0;
      clearIfCurrent();
    }
  });
});

resetBtn.addEventListener("click", () => {
  if (!resetArmed) {
    resetArmed = true;
    resetBtn.textContent = "再按一次確認清除";
    resetTimer = window.setTimeout(() => {
      resetArmed = false;
      resetBtn.textContent = "重新開始";
    }, 2500);
    return;
  }
  window.clearTimeout(resetTimer);
  resetArmed = false;
  resetBtn.textContent = "重新開始";
  resetAll();
});

restore();
update({ save: false });
booted = true;
