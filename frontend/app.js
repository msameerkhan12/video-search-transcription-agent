// Talks to the FastAPI backend's single POST /run endpoint.
// The backend runs the whole pipeline synchronously and returns a full
// steps_log at the end (no websockets needed, per the project brief).
// We animate through that log on arrival so the four stages still read as
// a sequence rather than a single freeze-then-dump.

const API_BASE_URL = window.API_BASE_URL || "http://localhost:8000";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const queryInput = document.getElementById("queryInput");
const runBtn = document.getElementById("runBtn");
const resetBtn = document.getElementById("resetBtn");
const copyBtn = document.getElementById("copyBtn");
const pipelineEl = document.getElementById("pipeline");
const errorBanner = document.getElementById("errorBanner");
const resultEl = document.getElementById("result");
const thumbWrap = document.getElementById("thumbWrap");
const resultThumb = document.getElementById("resultThumb");
const playOverlay = document.getElementById("playOverlay");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const resultTranscript = document.getElementById("resultTranscript");
const resultPath = document.getElementById("resultPath");
const toggleBtn = document.getElementById("toggleBtn");
const thumbRow= document.getElementById("thumbRow")
const kbList = document.getElementById("kbList");
const kbRefreshBtn = document.getElementById("kbRefreshBtn");
const kbToggleBtn = document.getElementById("kbToggleBtn");

const STEP_ORDER = ["search", "extract", "transcribe", "save"];
const STEP_TOOL_NAMES = {
  search: "VideoSearchTool",
  extract: "AudioExtractionTool",
  transcribe: "TranscriptionTool",
  save: "KnowledgeBaseWriter",
};

let previewTranscript = "";
let fullTranscript = "";
let showingFull = false;
let currentVideoId = null;
let kbCollapsed = false;

function stepEl(step) {
  return pipelineEl.querySelector(`[data-step="${step}"]`);
}

function setStepState(step, state, detail) {
  const el = stepEl(step);
  el.classList.remove("pending", "active", "done", "failed");
  el.classList.add(state);
  if (detail !== undefined) {
    el.querySelector(".step-detail").textContent = detail;
  }
}

function resetPipeline() {
  STEP_ORDER.forEach((step) => setStepState(step, "pending", "Waiting to start…"));
  pipelineEl.classList.add("visible");
  errorBanner.classList.remove("visible");
  resultEl.classList.remove("visible");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function extractYouTubeId(url) {
  if (!url) return null;
  const match = url.match(/(?:v=|youtu\.be\/|embed\/)([\w-]{11})/);
  return match ? match[1] : null;
}

async function animateLog(stepsLog) {
  const pause = REDUCED_MOTION ? 0 : 350;

  for (const step of STEP_ORDER) {
    setStepState(step, "active");
    await sleep(pause);

    const logEntry = stepsLog.find((entry) => entry.tool === STEP_TOOL_NAMES[step]);

    if (!logEntry) {
      setStepState(step, "pending", "Skipped — pipeline stopped earlier.");
      continue;
    }

    if (logEntry.output.startsWith("FAILED")) {
      setStepState(step, "failed", logEntry.output.replace("FAILED: ", ""));
      return;
    }

    setStepState(step, "done", logEntry.output);
  }
}

// Rebuilds the thumbnail box back to the static image + play button.
// Called whenever a new result comes in, so an old embedded player
// (and its audio) doesn't linger from the previous run.
function resetThumbToImage(videoId, title) {
  thumbRow.classList.remove("playing");
  thumbWrap.innerHTML = `
    <img id="resultThumb" alt="${title}" src="${
      videoId ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg` : ""
    }" />
    <button class="play-overlay" id="playOverlay" aria-label="Play video"></button>
  `;
  document.getElementById("playOverlay").addEventListener("click", playVideo);
}

// Swaps the static thumbnail for a live YouTube iframe embed, autoplaying.
function playVideo() {
  if (!currentVideoId) return;
  thumbRow.classList.add("playing");
  thumbWrap.innerHTML = `
    <iframe
      src="https://www.youtube.com/embed/${currentVideoId}?autoplay=1"
      title="YouTube video player"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowfullscreen
    ></iframe>
  `;
}

function showResult(data) {
  currentVideoId = extractYouTubeId(data.video_meta.video_url);
  resetThumbToImage(currentVideoId, data.video_meta.title);

  resultTitle.textContent = data.video_meta.title;
  resultMeta.textContent = `${data.video_meta.channel} · ${data.video_meta.duration}`;

  previewTranscript = data.transcript_preview;
  fullTranscript = data.transcript_full || data.transcript_preview;
  showingFull = false;
  resultTranscript.textContent = previewTranscript;
  toggleBtn.textContent = "Show full";

  resultPath.textContent = `Saved to ${data.transcript_path}`;
  resultEl.classList.add("visible");
}

function toggleTranscript() {
  showingFull = !showingFull;
  resultTranscript.textContent = showingFull ? fullTranscript : previewTranscript;
  toggleBtn.textContent = showingFull ? "Show preview" : "Show full";
}

async function copyTranscript() {
  try {
    await navigator.clipboard.writeText(resultTranscript.textContent);
    copyBtn.textContent = "Copied";
    setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
  } catch {
    copyBtn.textContent = "Couldn't copy";
    setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
  }
}

function resetForNewSearch() {
  pipelineEl.classList.remove("visible");
  errorBanner.classList.remove("visible");
  resultEl.classList.remove("visible");
  resetThumbToImage(currentVideoId, resultTitle.textContent); // kills any playing iframe
  currentVideoId = null;
  queryInput.value = "";
  queryInput.focus();
}

async function runPipeline() {
  const query = queryInput.value.trim();
  if (!query) {
    queryInput.focus();
    return;
  }

  runBtn.disabled = true;
  runBtn.textContent = "Running…";
  resetPipeline();

  try {
    const response = await fetch(`${API_BASE_URL}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    const data = await response.json();
    await animateLog(data.steps_log || []);

    if (!data.success) {
      errorBanner.textContent = `Failed at "${data.failed_step}" step: ${data.error}`;
      errorBanner.classList.add("visible");
    } else {
      showResult(data);
      loadKnowledgeBase(); // refresh the list so the new entry shows up
    }
  } catch (err) {
    errorBanner.textContent = `Could not reach the backend at ${API_BASE_URL}. Is it running? (${err.message})`;
    errorBanner.classList.add("visible");
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run";
  }
}

// --- Knowledge base panel ---

async function loadKnowledgeBase() {
  kbList.innerHTML = `<div class="kb-empty">Loading…</div>`;
  try {
    const res = await fetch(`${API_BASE_URL}/knowledge_base`);
    const entries = await res.json();
    renderKnowledgeBase(entries);
  } catch {
    kbList.innerHTML = `<div class="kb-empty">Couldn't load knowledge base.</div>`;
  }
}

function renderKnowledgeBase(entries) {
  if (!entries.length) {
    kbList.innerHTML = `<div class="kb-empty">No saved transcripts yet.</div>`;
    return;
  }
  kbList.innerHTML = "";
  entries.forEach((entry) => {
    const videoId = extractYouTubeId(entry.video_url);

    const item = document.createElement("div");
    item.className = "kb-item";

    // Thumbnail — only rendered if we have a video id. Clicking it plays
    // the video inline, independently of the text button next to it.
    const thumb = document.createElement("div");
    thumb.className = "kb-item-thumb";
    if (videoId) {
      thumb.innerHTML = `
        <img src="https://img.youtube.com/vi/${videoId}/mqdefault.jpg" alt="" />
        <button class="kb-play-overlay" aria-label="Play video"></button>
      `;
      thumb.querySelector(".kb-play-overlay").addEventListener("click", (e) => {
        e.stopPropagation();
        playKBThumb(thumb, videoId);
      });
    }

    // Text portion — clicking this still loads the saved transcript,
    // same behavior as before.
    const text = document.createElement("button");
    text.className = "kb-item-text";
    text.innerHTML = `
      <div class="kb-item-title">${entry.title}</div>
      <div class="kb-item-meta">${[entry.channel, entry.duration].filter(Boolean).join(" · ")}</div>
    `;
    text.addEventListener("click", () => loadKBEntry(entry.file_name));

    item.appendChild(thumb);
    item.appendChild(text);
    kbList.appendChild(item);
  });
}

// Swaps one KB item's thumbnail for a live autoplaying iframe, scoped to
// that single item so playing one entry doesn't affect the others.
function playKBThumb(thumbEl, videoId) {
  thumbEl.innerHTML = `
    <iframe
      src="https://www.youtube.com/embed/${videoId}?autoplay=1"
      title="YouTube video player"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowfullscreen
    ></iframe>
  `;
}

async function loadKBEntry(fileName) {
  try {
    const res = await fetch(`${API_BASE_URL}/knowledge_base/${encodeURIComponent(fileName)}`);
    const record = await res.json();
    if (record.error) throw new Error(record.error);
    showResultFromRecord(record, fileName);
  } catch (err) {
    errorBanner.textContent = `Could not load "${fileName}" (${err.message})`;
    errorBanner.classList.add("visible");
  }
}

function showResultFromRecord(record, fileName) {
  errorBanner.classList.remove("visible");
  pipelineEl.classList.remove("visible");
  const transcriptText = record.transcript?.text || "";
  showResult({
    video_meta: record.video,
    transcript_path: fileName,
    transcript_preview: transcriptText.slice(0, 300) + (transcriptText.length > 300 ? "..." : ""),
    transcript_full: transcriptText,
  });
}

function toggleKB() {
  kbCollapsed = !kbCollapsed;
  kbList.classList.toggle("collapsed", kbCollapsed);
  kbToggleBtn.textContent = kbCollapsed ? "Expand" : "Collapse";
}

runBtn.addEventListener("click", runPipeline);
resetBtn.addEventListener("click", resetForNewSearch);
copyBtn.addEventListener("click", copyTranscript);
toggleBtn.addEventListener("click", toggleTranscript);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runPipeline();
});
kbRefreshBtn.addEventListener("click", loadKnowledgeBase);
kbToggleBtn.addEventListener("click", toggleKB);
loadKnowledgeBase();