<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, putBytes } from '@/api/http'
import { useIsMobile } from '@/composables/useMediaQuery'
import { applyHead } from '@/router/head'
import QrCode from '@/components/ui/QrCode.vue'
import '@/styles/account.css'

// /deals/:id/record: the seller's live video (design/record-1…4-mobile).
// Camera only: getUserMedia + MediaRecorder, never a file picker. 20 seconds
// minimum ("Too short. Keep going."), stops itself at 60. Review, then Retake
// or Send: a resumable upload in 1 MB chunks to a signed URL; the server
// checks the recording is fresh and stamps it. On desktop the camera is
// hidden and the page shows the QR code to open this page on a phone.
// TODO: the idle "start" button and the permission/upload errors have no
// design yet; they reuse the recording screen's parts.
const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const MIN = 20
const MAX = 60
const DEFAULT_CHECKLIST = ['Front', 'Back', 'All sides', 'Switched on']
const CHIP_ITEMS = { 'Show the back': 'Back', 'Switch it on': 'Switched on', Closer: 'Closer', 'Better light': 'Better light' }

const id = computed(() => route.params.id)
const deal = ref(null)
const phase = ref('starting') // starting | ready | recording | review | sending | error
const error = ref('')
const elapsed = ref(0)
const tooShort = ref(false)
const progress = ref(0)
const recordedAt = ref(null)

const preview = useTemplateRef('preview')
const playback = useTemplateRef('playback')
let stream = null
let recorder = null
let chunks = []
let blob = null
let blobUrl = ''
let startedAt = 0
let clock = null
let shortTimer = null

const n = computed(() => (deal.value ? deal.value.video_count + 1 : 1))
const requested = computed(() => deal.value?.requested || null)
const checklist = computed(() => {
  const asked = (requested.value?.chips || []).map((c) => CHIP_ITEMS[c]).filter(Boolean)
  return [...new Set(['Front', ...asked, ...DEFAULT_CHECKLIST])].slice(0, 4)
})
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
const recordUrl = computed(() => `${window.location.origin}/deals/${id.value}/record`)
const stampText = computed(() => {
  if (!recordedAt.value) return ''
  const d = recordedAt.value
  const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
  const time = `${d.getHours() % 12 || 12}:${String(d.getMinutes()).padStart(2, '0')} ${d.getHours() < 12 ? 'AM' : 'PM'}`
  const area = deal.value?.listing.area ? ` · ${deal.value.listing.area.toUpperCase()}` : ''
  return `${fmt(elapsed.value)} RECORDED · ${d.getDate()} ${months[d.getMonth()]} ${time}${area}`
})

function pickType() {
  const types = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4']
  return types.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || ''
}

async function openCamera() {
  phase.value = 'starting'
  error.value = ''
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    phase.value = 'error'
    error.value = 'This browser can’t record video. Open buysafe in Chrome or Safari on your phone.'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: true })
  } catch {
    phase.value = 'error'
    error.value = 'We need your camera to record the live video. Allow camera access, then try again.'
    return
  }
  if (preview.value) {
    preview.value.srcObject = stream
    preview.value.play().catch(() => {})
  }
  phase.value = 'ready'
}

function closeCamera() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
}

function start() {
  chunks = []
  const type = pickType()
  recorder = new MediaRecorder(stream, { ...(type ? { mimeType: type } : {}), videoBitsPerSecond: 2_500_000 })
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
  recorder.onstop = finish
  recorder.start(1000)
  startedAt = Date.now()
  recordedAt.value = new Date()
  elapsed.value = 0
  phase.value = 'recording'
  clock = setInterval(() => {
    elapsed.value = (Date.now() - startedAt) / 1000
    if (elapsed.value >= MAX) stop(true)
  }, 250)
}

function stop(force = false) {
  if (phase.value !== 'recording') return
  if (!force && elapsed.value < MIN) {
    tooShort.value = true
    clearTimeout(shortTimer)
    shortTimer = setTimeout(() => (tooShort.value = false), 3000)
    return
  }
  clearInterval(clock)
  elapsed.value = Math.min(MAX, (Date.now() - startedAt) / 1000)
  tooShort.value = false
  recorder.stop()
}

function finish() {
  blob = new Blob(chunks, { type: (recorder.mimeType || 'video/webm').split(';')[0] })
  if (blobUrl) URL.revokeObjectURL(blobUrl)
  blobUrl = URL.createObjectURL(blob)
  closeCamera()
  phase.value = 'review'
}

const reviewPlaying = ref(false)
function playReview() {
  if (!playback.value) return
  playback.value.src = blobUrl
  playback.value.play()
  reviewPlaying.value = true
}

async function retake() {
  blob = null
  reviewPlaying.value = false
  await openCamera()
}

async function send() {
  phase.value = 'sending'
  progress.value = 0
  error.value = ''
  const mime = blob.type || 'video/webm'
  const init = await api(`/deals/${id.value}/videos/`, {
    method: 'POST',
    body: { action: 'init', size: blob.size, mime, duration: elapsed.value, captured_at: recordedAt.value.toISOString() },
  })
  if (!init.ok) return failSend(init.data?.detail)
  const { upload_url: url, chunk_size: size, upload_id: uploadId } = init.data
  const path = url.replace(/^\/api/, '')
  let offset = 0
  let retries = 0
  while (offset < blob.size) {
    const end = Math.min(offset + size, blob.size)
    const res = await putBytes(path, blob.slice(offset, end), { 'Content-Range': `bytes ${offset}-${end - 1}/${blob.size}` })
    if (res.ok) {
      offset = res.data.offset
      retries = 0
      progress.value = offset / blob.size
    } else if (res.status === 409 && res.data?.offset != null) {
      offset = res.data.offset // resume where the server is
    } else if (retries < 5) {
      retries += 1
      await new Promise((r) => setTimeout(r, 1000 * 2 ** retries))
      const check = await api(path)
      if (check.ok) offset = check.data.offset
    } else {
      return failSend()
    }
  }
  const done = await api(`/deals/${id.value}/videos/`, { method: 'POST', body: { action: 'complete', upload_id: uploadId } })
  if (!done.ok) return failSend(done.data?.detail)
  router.replace(`/deals/${id.value}`)
}

function failSend(detail) {
  phase.value = 'review'
  error.value = detail || 'The video didn’t send. Check your connection and try again.'
}

onMounted(async () => {
  const res = await api(`/deals/${id.value}/`)
  if (!res.ok) return router.replace('/deals')
  deal.value = res.data
  applyHead({ title: 'Record your live video' })
  if (!res.data.can.record) return router.replace(`/deals/${id.value}`)
  if (isMobile.value) openCamera()
})

onBeforeUnmount(() => {
  clearInterval(clock)
  clearTimeout(shortTimer)
  if (recorder && recorder.state !== 'inactive') {
    recorder.onstop = null
    recorder.stop()
  }
  closeCamera()
  if (blobUrl) URL.revokeObjectURL(blobUrl)
})
</script>

<template>
  <!-- ================= Desktop: open this on a phone ================= -->
  <div v-if="!isMobile" class="acct rv-desk">
    <main id="main" class="acct-wrap rv-desk__main">
      <RouterLink :to="`/deals/${id}`" class="acct-back">←  Back to the deal</RouterLink>
      <div v-if="deal" class="rv-desk__card">
        <div class="rv-desk__text">
          <span class="rv-desk__k">{{ n === 1 ? 'YOUR FIRST MESSAGE · VIDEO 1 OF 3' : `YOUR TURN · VIDEO ${n} OF 3` }}</span>
          <h1 class="rv-desk__h">Record on your phone.</h1>
          <span class="rv-desk__list"><span class="rv-show">SHOW</span><span v-for="c in checklist" :key="c">{{ c }}</span></span>
          <span class="rv-desk__rules">20–60 SECONDS · CAMERA ONLY · NO UPLOADS</span>
          <span class="rv-desk__link num">{{ recordUrl }}</span>
        </div>
        <div class="rv-desk__qr">
          <QrCode :value="recordUrl" :size="132" label="QR code: open the camera on your phone" class="rv-qr" />
          <span class="rv-desk__scan">Scan to record on your phone</span>
        </div>
      </div>
    </main>
  </div>

  <!-- ================= Phone: the camera ================= -->
  <div v-else class="rv vid">
    <div class="rv-top">
      <RouterLink :to="`/deals/${id}`" class="rv-close" aria-label="Close camera">×</RouterLink>
      <span v-if="phase === 'review' || phase === 'sending'" class="rv-rec num"><span class="rv-dot rv-dot--off"></span>STOPPED {{ fmt(elapsed) }}</span>
      <span v-else class="rv-rec num" role="timer"><span class="rv-dot"></span>REC {{ fmt(elapsed) }} / 1:00</span>
      <span class="rv-n">VIDEO {{ n }} OF 3</span>
    </div>

    <div v-if="requested && phase !== 'review' && phase !== 'sending'" class="rv-ask">
      <span class="rv-ask__k">{{ deal.buyer_first_name.toUpperCase() }} ASKED FOR</span>
      <span v-if="requested.chips.length" class="rv-ask__chips">{{ requested.chips.join(' · ') }}</span>
      <span v-if="requested.note" class="rv-ask__note">“{{ requested.note }}”</span>
    </div>

    <div class="rv-view">
      <video v-show="phase !== 'review' && phase !== 'sending'" ref="preview" class="rv-video" muted playsinline></video>
      <video v-show="(phase === 'review' || phase === 'sending') && reviewPlaying" ref="playback" class="rv-video" playsinline controls></video>
      <span class="rv-corner rv-corner--tl"></span>
      <span class="rv-corner rv-corner--tr"></span>
      <span class="rv-corner rv-corner--bl"></span>
      <span class="rv-corner rv-corner--br"></span>
      <span v-if="phase === 'starting' || phase === 'error'" class="rv-placeholder">LIVE CAMERA · BACK LENS</span>
      <button
        v-if="(phase === 'review' || phase === 'sending') && !reviewPlaying"
        type="button"
        class="rv-play"
        aria-label="Play your video"
        @click="playReview"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="#121410" /></svg>
      </button>
      <div v-if="tooShort" role="alert" class="rv-short">
        <span class="rv-short__h">Too short. Keep going.</span>
        <span class="rv-short__p">Videos need at least 20 seconds so {{ deal?.buyer_first_name }} can see everything.</span>
      </div>
      <div v-if="phase === 'error'" role="alert" class="rv-short">
        <span class="rv-short__p">{{ error }}</span>
      </div>
    </div>

    <template v-if="phase === 'review' || phase === 'sending'">
      <div class="rv-review">
        <span class="rv-stamp num">{{ stampText }}</span>
        <p v-if="error" class="rv-error" role="alert">{{ error }}</p>
        <div class="rv-review__btns">
          <button type="button" class="rv-retake" :disabled="phase === 'sending'" @click="retake">Retake</button>
          <button type="button" class="rv-send" :disabled="phase === 'sending'" @click="send">
            Send video {{ n }} of 3
            <span v-if="phase === 'sending'" class="rv-send__bar" :style="{ transform: `scaleX(${progress})` }" aria-hidden="true"></span>
          </button>
        </div>
        <span class="rv-unlock">Your chat unlocks once {{ deal?.buyer_first_name }} rates it Good.</span>
      </div>
    </template>
    <template v-else>
      <div class="rv-check">
        <span class="rv-show">SHOW</span>
        <span v-for="item in checklist" :key="item">{{ item }}</span>
      </div>
      <div class="rv-controls">
        <button
          v-if="phase === 'recording'"
          type="button"
          class="rv-stop"
          aria-label="Stop recording"
          @click="stop()"
        >
          <span class="rv-stop__sq"></span>
        </button>
        <button
          v-else-if="phase === 'error'"
          type="button"
          class="rv-stop"
          aria-label="Try the camera again"
          @click="openCamera"
        >
          <span class="rv-stop__dot"></span>
        </button>
        <button v-else type="button" class="rv-stop" aria-label="Start recording" :disabled="phase !== 'ready'" @click="start">
          <span class="rv-stop__dot"></span>
        </button>
      </div>
      <span class="rv-hint">20–60 seconds. Camera only: videos can’t be picked from your gallery.</span>
    </template>
  </div>
</template>

<style scoped>
.vid {
  background-color: var(--ink);
  background-image: repeating-linear-gradient(135deg, rgba(243, 237, 224, 0.05) 0 10px, rgba(243, 237, 224, 0) 10px 20px);
}

.rv {
  position: fixed;
  inset: 0;
  z-index: 60;
  color: var(--paper);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.rv-top {
  flex-shrink: 0;
  padding: 12px 12px 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rv-close {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(243, 237, 224, 0.14);
  color: var(--paper);
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  font-size: 20px;
}

.rv-rec {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.55);
  padding: 8px 12px;
  border-radius: 999px;
}

.rv-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #e5484d;
}

.rv-dot--off {
  background: #8c8e85;
}

.rv-n {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 8px 10px;
  border-radius: 999px;
  background: var(--accent);
  color: var(--ink);
}

.rv-ask {
  flex-shrink: 0;
  margin: 4px 16px 0;
  background: rgba(0, 0, 0, 0.55);
  border-left: 4px solid #ff8a65;
  border-radius: 4px 12px 12px 4px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rv-ask__k {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #ff8a65;
}

.rv-ask__chips {
  font-size: 15px;
  font-weight: 700;
}

.rv-ask__note {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 16px;
  color: rgba(243, 237, 224, 0.85);
}

.rv-view {
  flex-grow: 1;
  min-height: 0;
  margin: 12px 16px 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rv-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
}

.rv-corner {
  position: absolute;
  width: 34px;
  height: 34px;
  border: 0 solid var(--accent);
  z-index: 1;
  pointer-events: none;
}

.rv-corner--tl {
  left: 0;
  top: 0;
  border-left-width: 3px;
  border-top-width: 3px;
  border-radius: 6px 0 0 0;
}

.rv-corner--tr {
  right: 0;
  top: 0;
  border-right-width: 3px;
  border-top-width: 3px;
  border-radius: 0 6px 0 0;
}

.rv-corner--bl {
  left: 0;
  bottom: 0;
  border-left-width: 3px;
  border-bottom-width: 3px;
  border-radius: 0 0 0 6px;
}

.rv-corner--br {
  right: 0;
  bottom: 0;
  border-right-width: 3px;
  border-bottom-width: 3px;
  border-radius: 0 0 6px 0;
}

.rv-placeholder {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: rgba(243, 237, 224, 0.45);
}

.rv-play {
  position: relative;
  z-index: 1;
  width: 64px;
  height: 64px;
  border: 0;
  border-radius: 50%;
  background: rgba(243, 237, 224, 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.rv-short {
  position: absolute;
  z-index: 2;
  left: 20px;
  right: 20px;
  bottom: 20px;
  background: var(--paper);
  color: var(--ink);
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rv-short__h {
  font-size: 15px;
  font-weight: 800;
}

.rv-short__p {
  font-size: 13px;
  color: var(--ink-2);
}

.rv-check {
  flex-shrink: 0;
  margin: 12px 16px 0;
  background: rgba(0, 0, 0, 0.55);
  border-radius: 14px;
  padding: 12px 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  font-size: 13px;
}

/* What to film: a prompt, not a checklist. Nothing checks it (the buyer's
   rating does), so no ticks or boxes that look like they get verified. */
.rv-check {
  color: rgba(243, 237, 224, 0.85);
}

.rv-show {
  grid-column: 1 / -1;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  opacity: 0.75;
}

.rv-controls {
  flex-shrink: 0;
  padding: 20px 0 10px;
  display: flex;
  justify-content: center;
}

.rv-stop {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 4px solid var(--paper);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.rv-stop:disabled {
  opacity: 0.5;
}

.rv-stop__sq {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: #e5484d;
}

.rv-stop__dot {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: #e5484d;
}

.rv-hint {
  flex-shrink: 0;
  padding: 0 28px calc(24px + env(safe-area-inset-bottom, 0px));
  text-align: center;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(243, 237, 224, 0.7);
}

.rv-review {
  flex-shrink: 0;
  padding: 18px 16px calc(26px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rv-stamp {
  text-align: center;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: rgba(243, 237, 224, 0.75);
}

.rv-error {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: #ff8a65;
}

.rv-review__btns {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 10px;
}

.rv-retake,
.rv-send {
  height: 56px;
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  cursor: pointer;
}

.rv-retake {
  border: 1.5px solid rgba(243, 237, 224, 0.5);
  background: transparent;
  color: var(--paper);
  font-weight: 600;
}

.rv-send {
  position: relative;
  overflow: hidden;
  border: 0;
  background: var(--accent);
  color: var(--ink);
  font-weight: 700;
}

.rv-send__bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 4px;
  background: var(--ink);
  transform-origin: left;
  transition: transform 0.3s;
}

.rv-unlock {
  text-align: center;
  font-size: 12px;
  color: rgba(243, 237, 224, 0.6);
}

.rv :is(a, button):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* ---- Desktop ---- */

.rv-desk__main {
  padding-top: 32px;
  padding-bottom: 96px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: flex-start;
}

.rv-desk__card {
  width: 620px;
  max-width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 2px solid var(--accent);
  border-radius: 18px;
  padding: 22px 24px;
  display: grid;
  grid-template-columns: 1fr 150px;
  gap: 24px;
  align-items: center;
}

.rv-desk__text {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.rv-desk__k {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.rv-desk__h {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.rv-desk__list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  font-size: 14px;
  color: var(--ink-2);
}

.rv-desk__rules,
.rv-desk__link {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.rv-desk__qr {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.rv-qr {
  border-radius: 8px;
  border: 8px solid #ffffff;
  box-shadow: 0 0 0 1.5px rgba(18, 20, 16, 0.2);
  box-sizing: content-box;
}

.rv-desk__scan {
  font-size: 12px;
  line-height: 1.35;
  text-align: center;
  color: var(--ink-2);
}
</style>
