<script setup>
import { computed, ref, watch } from 'vue'
import { naira } from '@/utils/format'
import { REFUND_ARRIVES } from '@/config/payments'
import { REFUND_REASONS, clock, dayClock, meetupWhen, shortDayClock, shortTitle, stamp } from '@/utils/deals'
import QrCode from '@/components/ui/QrCode.vue'

// The deal chat (design/deal-01…11-*): every message kind, then the card for
// whatever the deal is waiting on (record prompt, waiting placeholder, rating,
// what to show, the 3rd-Bad decision, the closing receipt).
const props = defineProps({
  deal: { type: Object, required: true },
  messages: { type: Array, required: true },
  mobile: { type: Boolean, default: false },
  recordUrl: { type: String, required: true },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['rate', 'decide', 'confirm-meetup', 'picking'])

const CHIPS = ['Show the back', 'Switch it on', 'Closer', 'Better light']
const CHECKLIST = ['Front', 'Back', 'All sides', 'Switched on']

const d = computed(() => props.deal)
const buyer = computed(() => d.value.buyer_first_name)
const seller = computed(() => d.value.seller_first_name)
const up = (s) => (s || '').toUpperCase()
const item = computed(() => shortTitle(d.value.listing.title))
const isBuyer = computed(() => d.value.role === 'buyer')
const current = computed(() => d.value.video_count) // the video being rated
const nextN = computed(() => d.value.video_count + 1) // the video being recorded
const duration = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
const hoursMinutes = (s) => {
  const m = Math.max(0, Math.floor((s || 0) / 60))
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`
}

// ---- Rating: Good / Bad, then what to show ----

const picking = ref(false)
const chips = ref([])
const note = ref('')
// Reset only when the deal moves on. (Watching a getter that returns a new
// array would fire on every poll and close the form mid-typing.)
watch(
  [() => d.value.state, () => d.value.video_count],
  () => {
    picking.value = false
    chips.value = []
    note.value = ''
  },
)
watch(picking, (value) => emit('picking', value))

function bad() {
  // The 3rd Bad goes straight to the refund-or-continue choice.
  if (current.value >= 3) emit('rate', { verdict: 'bad', chips: [], note: '' })
  else picking.value = true
}
function toggle(chip) {
  chips.value = chips.value.includes(chip) ? chips.value.filter((c) => c !== chip) : [...chips.value, chip]
}
function ask() {
  emit('rate', { verdict: 'bad', chips: chips.value, note: note.value.trim() })
}

// ---- Playing a video inline ----

const playing = ref(null)

// ---- Messages ----

function systemLine(m) {
  const data = m.data || {}
  switch (m.event) {
    case 'paid':
      return {
        tone: 'green',
        text: props.mobile
          ? `${up(buyer.value)} PAID ${naira(data.amount)} · HELD · ${clock(m.created_at)}`
          : `${up(buyer.value)} PAID ${naira(data.amount)} · HELD IN ESCROW · ${clock(m.created_at)}`,
      }
    case 'video_missed':
      return {
        tone: 'red',
        text: props.mobile
          ? `NO LIVE VIDEO WITHIN ${data.hours} HOURS`
          : `${data.hours} HOURS PASSED WITHOUT A LIVE VIDEO FROM ${up(seller.value)}`,
      }
    case 'chat_unlocked':
      return {
        tone: 'green',
        text: props.mobile ? 'CHAT UNLOCKED · CONTACTS CAN BE SHARED' : 'CHAT UNLOCKED · CONTACT DETAILS CAN NOW BE SHARED',
      }
    case 'no_show':
      return { tone: 'red', text: 'CANCELLED AFTER A NO-SHOW REPORT' }
    default:
      return null
  }
}

const items = computed(() =>
  props.messages
    .map((m) => {
      if (m.kind === 'system') {
        const line = systemLine(m)
        return line && { ...m, view: 'pill', ...line }
      }
      if (m.kind === 'rating') {
        if (m.data.verdict === 'bad') return null
        return {
          ...m,
          view: 'pill',
          tone: 'green',
          text: props.mobile
            ? 'CHAT UNLOCKED · CONTACTS CAN BE SHARED'
            : 'VIDEO ACCEPTED · CHAT UNLOCKED · CONTACT DETAILS CAN NOW BE SHARED',
        }
      }
      if (m.kind === 'meetup' && (!m.meetup || m.meetup.status === 'cancelled')) return null
      return { ...m, view: m.kind }
    })
    .filter(Boolean),
)

function caption(video) {
  switch (video.verdict) {
    case 'good':
      return { tone: 'green', text: `✓ ${up(buyer.value)} RATED IT GOOD` }
    case 'auto_good':
      return { tone: 'green', text: '✓ NOT RATED IN TIME · COUNTS AS GOOD' }
    case 'bad':
      return { tone: 'red', text: `✕ ${up(buyer.value)} RATED IT BAD` }
    default:
      return { tone: 'muted', text: props.mobile ? '✓ CAPTURED LIVE' : '✓ CAPTURED LIVE, NOT UPLOADED' }
  }
}

const reason = computed(() => REFUND_REASONS[d.value.refund?.reason]?.long || '')
const buyerName = computed(() => {
  const who = isBuyer.value ? d.value.me : d.value.other
  return `${who.first_name} ${who.last_initial}.`
})
</script>

<template>
  <div class="ch" :class="{ 'ch--m': mobile }">
    <template v-for="m in items" :key="m.id">
      <!-- System pill -->
      <div v-if="m.view === 'pill'" class="ch-row ch-row--center">
        <span class="ch-pill" :class="`ch-pill--${m.tone}`">{{ m.text }}</span>
      </div>

      <!-- Text -->
      <div v-else-if="m.view === 'text'" class="ch-row" :class="{ 'ch-row--mine': m.mine }">
        <div class="ch-bubble" :class="{ 'ch-bubble--mine': m.mine }">
          {{ m.body }}<span class="ch-time num">{{ stamp(m.created_at) }}{{ m.mine && m.read_at ? ' · READ' : '' }}</span>
        </div>
      </div>

      <!-- Photo (not designed yet: the text bubble's frame around the picture) -->
      <div v-else-if="m.view === 'photo'" class="ch-row" :class="{ 'ch-row--mine': m.mine }">
        <a :href="m.photo_url" target="_blank" rel="noopener" class="ch-photo" :class="{ 'ch-bubble--mine': m.mine }">
          <img :src="m.photo_url" alt="Photo" loading="lazy" />
          <span class="ch-time num">{{ stamp(m.created_at) }}{{ m.mine && m.read_at ? ' · READ' : '' }}</span>
        </a>
      </div>

      <!-- Live video -->
      <div v-else-if="m.view === 'live_video' && m.video" class="ch-row" :class="{ 'ch-row--mine': m.mine }">
        <div class="ch-video-wrap" :class="{ 'ch-video-wrap--mine': m.mine }">
          <div class="ch-video vid">
            <video
              v-if="playing === m.video.n"
              class="ch-video__el"
              :src="m.video.url"
              :type="m.video.mime"
              controls
              autoplay
              playsinline
            ></video>
            <template v-else>
              <img v-if="m.video.thumb_url" class="ch-video__thumb" :src="m.video.thumb_url" alt="" />
              <span class="ch-video__badge num">
                <span class="ch-video__rec" aria-hidden="true"></span>{{ mobile ? '' : 'LIVE ' }}VIDEO {{ m.video.n }} OF 3 · {{ duration(m.video.duration) }}
              </span>
              <button type="button" class="ch-video__play" :aria-label="`Play live video ${m.video.n} of 3`" @click="playing = m.video.n">
                <svg :width="mobile ? 16 : 22" :height="mobile ? 16 : 22" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="#121410" /></svg>
              </button>
              <span v-if="!mobile" class="ch-video__stamp num">{{ m.video.overlay_text }}</span>
            </template>
          </div>
          <span class="ch-caption" :class="`ch-caption--${caption(m.video).tone}`">{{ caption(m.video).text }}</span>
        </div>
      </div>

      <!-- What the buyer asked for after a Bad -->
      <div v-else-if="m.view === 'instruction'" class="ch-row" :class="{ 'ch-row--mine': m.mine }">
        <div class="ch-ask">
          <span class="ch-ask__k">{{ m.mine ? 'YOU' : up(buyer) }} ASKED FOR VIDEO {{ m.data.next_n }}</span>
          <span v-if="m.data.chips.length" class="ch-ask__chips">{{ m.data.chips.join(' · ') }}</span>
          <span v-if="m.data.note" class="ch-ask__note">“{{ m.data.note }}”</span>
        </div>
      </div>

      <!-- Meetup -->
      <div v-else-if="m.view === 'meetup'" class="ch-row ch-row--center">
        <div class="ch-meet">
          <span v-if="m.meetup.status === 'confirmed'" class="ch-meet__k">MEETUP · CONFIRMED BY BOTH</span>
          <span v-else class="ch-meet__k ch-meet__k--amber">MEETUP · PROPOSED BY {{ m.mine ? 'YOU' : up(isBuyer ? seller : buyer) }}</span>
          <template v-if="mobile">
            <span class="ch-meet__when">{{ meetupWhen(m.meetup.when) }} · {{ m.meetup.place }}</span>
          </template>
          <template v-else>
            <span class="ch-meet__when">{{ meetupWhen(m.meetup.when) }}</span>
            <span class="ch-meet__place">{{ m.meetup.place }}</span>
          </template>
          <button
            v-if="m.meetup.status === 'proposed' && !m.mine && deal.can.meetup"
            type="button"
            class="ch-meet__ok"
            :disabled="busy"
            @click="emit('confirm-meetup', m.meetup.id)"
          >
            Confirm meetup
          </button>
        </div>
      </div>
    </template>

    <!-- ===== What the deal is waiting on ===== -->

    <!-- Seller: record the live video (desktop: QR to the phone) -->
    <div v-if="deal.can.record" class="ch-row" :class="mobile ? 'ch-row--center' : 'ch-row--mine'">
      <div v-if="!mobile" id="record-prompt" class="ch-record">
        <div class="ch-record__text">
          <span class="ch-card-k">{{ nextN === 1 ? 'YOUR FIRST MESSAGE · VIDEO 1 OF 3' : `YOUR TURN · VIDEO ${nextN} OF 3` }}</span>
          <span class="ch-record__h">{{ nextN === 1 ? `Record a live video of the ${item}.` : `Record video ${nextN} with what ${buyer} asked for.` }}</span>
          <span class="ch-record__list"><span class="ch-record__show">SHOW</span><span v-for="c in CHECKLIST" :key="c">{{ c }}</span></span>
          <span class="ch-record__rules">20–60 SECONDS · CAMERA ONLY · NO UPLOADS</span>
        </div>
        <div class="ch-record__qr">
          <QrCode :value="recordUrl" :size="132" label="QR code: open the camera on your phone" class="ch-qr" />
          <span class="ch-record__scan">Scan to record on your phone</span>
        </div>
      </div>
      <div v-else class="ch-record-m">
        <span class="ch-card-k">{{ nextN === 1 ? 'YOUR FIRST MESSAGE · VIDEO 1 OF 3' : `VIDEO ${nextN} OF 3 · ${hoursMinutes(deal.seconds_left)} LEFT` }}</span>
        <span class="ch-record-m__h">{{ nextN === 1 ? `Record a live video of the ${item}.` : `Record video ${nextN} with what ${buyer} asked for.` }}</span>
        <span class="ch-record-m__rules">SHOW FRONT · BACK · ALL SIDES · SWITCHED ON · 20–60S</span>
        <RouterLink :to="`/deals/${deal.id}/record`" class="ch-record-m__btn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F3EDE0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="6" width="13" height="12" rx="2.5" /><path d="M15.5 10.5l6-3.5v10l-6-3.5z" /></svg>
          Record now
        </RouterLink>
      </div>
    </div>

    <!-- Buyer: waiting for the video -->
    <div v-else-if="isBuyer && deal.state === 'awaiting_video'" class="ch-row ch-row--center">
      <div class="ch-wait">
        <span class="ch-wait__h"><span class="ch-wait__dot" aria-hidden="true"></span>Waiting for {{ seller }}’s live video</span>
        <span v-if="!mobile" class="ch-wait__p">Keep typing. Tell {{ seller }} what you want to see. If no video arrives by {{ clock(deal.deadline) }}, you’re refunded in full automatically.</span>
        <span v-else class="ch-wait__p">Keep typing what you want to see. No video by {{ clock(deal.deadline) }} means a full refund.</span>
      </div>
    </div>

    <!-- Buyer: rate it -->
    <div v-else-if="deal.can.rate && !picking" class="ch-row" :class="{ 'ch-row--center': mobile }">
      <div class="ch-rate">
        <span class="ch-rate__head">
          <span class="ch-card-k">RATE VIDEO {{ current }} OF 3<template v-if="mobile"> · BY {{ clock(deal.deadline) }}</template></span>
          <span class="ch-rate__h">Does it show the {{ item }} clearly?</span>
          <span v-if="!mobile" class="ch-rate__p num">Rate it by {{ clock(deal.deadline) }}. If you don’t, it counts as Good.</span>
        </span>
        <div class="ch-two">
          <button type="button" class="ch-bad" :disabled="busy" @click="bad">{{ mobile ? 'Bad' : 'Bad, show me more' }}</button>
          <button type="button" class="ch-good" :disabled="busy" @click="emit('rate', { verdict: 'good' })">Good</button>
        </div>
        <span v-if="mobile" class="ch-rate__note">No rating in time counts as Good.</span>
      </div>
    </div>

    <!-- Buyer: what should the next video show? -->
    <div v-else-if="deal.can.rate && picking" class="ch-row" :class="{ 'ch-row--center': mobile }">
      <div class="ch-pick">
        <span class="ch-rate__head">
          <span v-if="!mobile" class="ch-card-k ch-card-k--red">VIDEO {{ current }} RATED BAD</span>
          <span class="ch-rate__h">{{ mobile ? `What should ${seller} show next?` : `What should ${seller} show in video ${current + 1}?` }}</span>
        </span>
        <div class="ch-chips">
          <button
            v-for="chip in CHIPS"
            :key="chip"
            type="button"
            class="ch-chip"
            :aria-pressed="chips.includes(chip)"
            @click="toggle(chip)"
          >
            {{ chip }}
          </button>
        </div>
        <textarea
          v-model="note"
          rows="2"
          maxlength="200"
          aria-label="Anything else?"
          placeholder="Anything else? e.g. the dent up close"
          class="ch-note"
        ></textarea>
        <div v-if="!mobile" class="ch-pick__foot">
          <span class="ch-pick__p">{{ seller }} gets 4 hours for video {{ current + 1 }} of 3.</span>
          <button type="button" class="ch-ask-btn" :disabled="busy || (!chips.length && !note.trim())" @click="ask">Ask for video {{ current + 1 }} of 3</button>
        </div>
        <button v-else type="button" class="ch-ask-btn" :disabled="busy || (!chips.length && !note.trim())" @click="ask">Ask for video {{ current + 1 }} of 3</button>
      </div>
    </div>

    <!-- Buyer: 3 bad videos, refund or continue -->
    <div v-else-if="deal.can.decide" class="ch-row ch-row--center">
      <div class="ch-decide">
        <span class="ch-rate__head">
          <span class="ch-card-k ch-card-k--red">3 OF 3 VIDEOS RATED BAD</span>
          <span class="ch-decide__h">{{ mobile ? 'What would you like to do?' : 'Still not right. What would you like to do?' }}</span>
        </span>
        <div class="ch-decide__opts">
          <button type="button" class="ch-opt ch-opt--refund" :disabled="busy" @click="emit('decide', 'refund')">
            <span class="ch-opt__h">Cancel for a full refund</span>
            <span class="ch-opt__p num">{{ naira(deal.amount) }} back to {{ deal.source.bank }} ····{{ deal.source.last4 }}{{ mobile ? '' : '. No fees.' }}</span>
          </button>
          <button type="button" class="ch-opt ch-opt--go" :disabled="busy" @click="emit('decide', 'continue')">
            <span class="ch-opt__h">Continue to the meetup</span>
            <span class="ch-opt__p">{{ mobile ? 'Money stays held until you confirm' : 'Check it in person. The money stays held until you confirm.' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Closed: the receipt -->
    <div v-if="deal.state === 'released' || deal.state === 'refunded'" class="ch-row ch-row--center">
      <div class="ch-receipt" :class="{ perf: !mobile }">
        <template v-if="deal.state === 'released' && deal.role === 'seller'">
          <span class="ch-receipt__k">YOU’VE BEEN PAID</span>
          <span class="ch-receipt__amt ch-receipt__amt--green num">{{ naira(deal.payout) }}</span>
          <span class="ch-receipt__p">Sent to your {{ deal.payout_account?.bank_name }} account ····{{ deal.payout_account?.last4 }}.</span>
          <div class="dash"></div>
          <div class="ch-receipt__row num"><span>Buyer paid</span><strong>{{ naira(deal.amount) }}</strong></div>
          <div class="ch-receipt__row num"><span>{{ mobile ? 'Fee' : 'buysafe fee' }} ({{ deal.fee_rate_label }})</span><strong>− {{ naira(deal.fee) }}</strong></div>
          <div v-if="!mobile" class="ch-receipt__row num"><span>Sent</span><strong>{{ dayClock(deal.released_at) }}</strong></div>
          <span class="ch-receipt__stamp ch-receipt__stamp--green">RELEASED</span>
        </template>
        <template v-else-if="deal.state === 'released'">
          <span class="ch-receipt__k">DEAL {{ deal.id }} · COMPLETE</span>
          <span class="ch-receipt__amt num">{{ naira(deal.amount) }}</span>
          <span class="ch-receipt__p">{{ mobile ? `Released from escrow to ${seller}.` : `Released from escrow to ${seller}. Thanks for buying safe.` }}</span>
          <div class="dash"></div>
          <div class="ch-receipt__row num"><span>Paid from</span><strong>{{ deal.source.bank }} ····{{ deal.source.last4 }}</strong></div>
          <div class="ch-receipt__row num"><span>Released</span><strong>{{ mobile ? shortDayClock(deal.released_at) : dayClock(deal.released_at) }}</strong></div>
          <div v-if="!mobile" class="ch-receipt__row num"><span>Deal</span><strong>BS-D-{{ String(deal.id).padStart(6, '0') }}</strong></div>
          <span class="ch-receipt__stamp ch-receipt__stamp--green">RELEASED</span>
        </template>
        <template v-else>
          <span class="ch-receipt__k">DEAL {{ deal.id }} · CANCELLED</span>
          <span class="ch-receipt__amt num">{{ naira(deal.amount) }}</span>
          <span class="ch-receipt__p">{{ mobile ? 'Refunded in full to the account it came from. No fees.' : 'Refunded in full to the account it came from. No fees: this wasn’t your fault.' }}</span>
          <div class="dash"></div>
          <div class="ch-receipt__row num">
            <span>Refunded to</span>
            <strong v-if="deal.refund?.bank && mobile">{{ deal.refund.bank }} ····{{ deal.refund.last4 }}</strong>
            <strong v-else-if="deal.refund?.bank">{{ buyerName }} · {{ deal.refund.bank }} ····{{ deal.refund.last4 }}</strong>
            <strong v-else>{{ buyerName }}</strong>
          </div>
          <div v-if="!mobile && reason" class="ch-receipt__row num"><span>Reason</span><strong>{{ reason }}</strong></div>
          <div class="ch-receipt__row num"><span>Arrives</span><strong>Within {{ REFUND_ARRIVES }}</strong></div>
          <span class="ch-receipt__stamp ch-receipt__stamp--red">REFUNDED</span>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ch {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ch--m {
  gap: 10px;
}

.ch-row {
  display: flex;
  justify-content: flex-start;
}

.ch-row--mine {
  justify-content: flex-end;
}

.ch-row--center {
  justify-content: center;
}

.vid {
  background-color: #1b1f1a;
  background-image: repeating-linear-gradient(135deg, rgba(243, 237, 224, 0.05) 0 10px, rgba(243, 237, 224, 0) 10px 20px);
}

.dash {
  border-top: 1.5px dashed rgba(18, 20, 16, 0.28);
}

.perf {
  position: relative;
}

.perf::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -10px;
  height: 20px;
  background: radial-gradient(circle at 10px 0, transparent 9px, #efe9dc 10px) 0 0 / 20px 20px repeat-x;
}

/* ---- Pills ---- */

.ch-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  padding: 6px 12px;
  border-radius: 999px;
  text-align: center;
}

.ch-pill--green {
  color: var(--released);
  background: rgba(30, 107, 69, 0.1);
}

.ch-pill--red {
  color: #a3361f;
  background: rgba(163, 54, 31, 0.08);
}

.ch--m .ch-pill {
  font-size: 9px;
  letter-spacing: 0.05em;
  padding: 5px 10px;
}

/* ---- Bubbles ---- */

.ch-bubble {
  max-width: 460px;
  background: #ffffff;
  color: var(--ink);
  padding: 12px 16px;
  border-radius: 16px 16px 16px 4px;
  font-size: 15px;
  line-height: 1.45;
  white-space: pre-line;
  overflow-wrap: anywhere;
}

.ch-bubble--mine {
  background: var(--ink);
  color: var(--paper);
  border-radius: 16px 16px 4px 16px;
}

.ch-time {
  display: block;
  margin-top: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: #8c8e85;
  text-align: left;
  white-space: nowrap;
}

.ch-bubble--mine .ch-time {
  color: #a9a99c;
  text-align: right;
}

.ch--m .ch-bubble {
  max-width: 280px;
  padding: 10px 13px;
  border-radius: 14px 14px 14px 4px;
  font-size: 14px;
}

.ch--m .ch-bubble--mine {
  border-radius: 14px 14px 4px 14px;
}

.ch--m .ch-time {
  margin-top: 3px;
  font-size: 9px;
}

.ch-photo {
  display: block;
  max-width: 280px;
  background: #ffffff;
  padding: 6px;
  border-radius: 16px 16px 16px 4px;
  text-decoration: none;
}

.ch-photo.ch-bubble--mine {
  border-radius: 16px 16px 4px 16px;
}

.ch-photo img {
  display: block;
  max-width: 100%;
  max-height: 320px;
  border-radius: 12px;
}

.ch-photo .ch-time {
  padding: 0 6px 2px;
}

/* ---- Live video ---- */

.ch-video-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}

.ch-video-wrap--mine {
  align-items: flex-end;
}

.ch-video {
  width: 220px;
  height: 290px;
  border-radius: 16px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ch-video__el,
.ch-video__thumb {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: #1b1f1a;
}

.ch-video__badge {
  position: absolute;
  left: 10px;
  top: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--paper);
  background: rgba(0, 0, 0, 0.5);
  padding: 5px 8px;
  border-radius: 999px;
}

.ch-video__rec {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #e5484d;
}

.ch-video__play {
  position: relative;
  width: 58px;
  height: 58px;
  border: 0;
  border-radius: 50%;
  background: rgba(243, 237, 224, 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.ch-video__stamp {
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 10px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  color: rgba(243, 237, 224, 0.8);
}

.ch-caption {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.ch-caption--green {
  color: var(--released);
}

.ch-caption--red {
  color: #a3361f;
}

.ch--m .ch-video-wrap {
  gap: 4px;
}

.ch--m .ch-video {
  width: 150px;
  height: 200px;
  border-radius: 14px;
}

.ch--m .ch-video__badge {
  left: 7px;
  top: 7px;
  gap: 4px;
  font-size: 8px;
  letter-spacing: 0;
  padding: 4px 6px;
}

.ch--m .ch-video__rec {
  width: 5px;
  height: 5px;
}

.ch--m .ch-video__play {
  width: 44px;
  height: 44px;
}

.ch--m .ch-caption {
  font-size: 9px;
  letter-spacing: 0.06em;
}

/* ---- Instruction ---- */

.ch-ask {
  max-width: 460px;
  background: #ffffff;
  border-left: 4px solid #a3361f;
  border-radius: 4px 14px 14px 4px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ch-ask__k {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: #a3361f;
}

.ch-ask__chips {
  font-size: 15px;
  font-weight: 700;
}

.ch-ask__note {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 18px;
  line-height: 1.3;
  color: var(--ink-2);
  overflow-wrap: anywhere;
}

.ch--m .ch-ask {
  max-width: 290px;
  border-radius: 4px 12px 12px 4px;
  padding: 10px 12px;
  gap: 3px;
}

.ch--m .ch-ask__k {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.ch--m .ch-ask__chips {
  font-size: 14px;
}

.ch--m .ch-ask__note {
  font-size: 16px;
}

/* ---- Meetup ---- */

.ch-meet {
  width: 420px;
  max-width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 1.5px solid var(--forest);
  border-radius: 16px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ch-meet__k {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--released);
}

.ch-meet__k--amber {
  color: var(--amber-ink);
}

.ch-meet__when {
  font-size: 20px;
  font-weight: 800;
}

.ch-meet__place {
  font-size: 14px;
  color: var(--ink-2);
}

.ch-meet__ok {
  align-self: flex-start;
  margin-top: 4px;
  height: 44px;
  padding: 0 16px;
  border: 0;
  border-radius: 10px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.ch--m .ch-meet {
  width: 100%;
  border-radius: 14px;
  padding: 12px 14px;
  gap: 3px;
}

.ch--m .ch-meet__k {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.ch--m .ch-meet__when {
  font-size: 16px;
}

/* ---- Cards ---- */

.ch-card-k {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--amber-ink);
}

.ch-card-k--red {
  color: #a3361f;
}

.ch--m .ch-card-k {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.ch-record {
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

.ch-record__text {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ch-record__h {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.ch-record__list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  font-size: 14px;
  color: var(--ink-2);
}

.ch-record__show {
  grid-column: 1 / -1;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.ch-record__rules {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.ch-record__qr {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.ch-qr {
  border-radius: 8px;
  border: 8px solid #ffffff;
  box-shadow: 0 0 0 1.5px rgba(18, 20, 16, 0.2);
  box-sizing: content-box;
}

.ch-record__scan {
  font-size: 12px;
  line-height: 1.35;
  text-align: center;
  color: var(--ink-2);
}

.ch-record-m {
  width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 2px solid var(--accent);
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ch-record-m__h {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.2;
}

.ch-record-m__rules {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
}

.ch-record-m__btn {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-decoration: none;
  background: var(--ink);
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
}

.ch .ch-record-m__btn,
.ch .ch-record-m__btn:hover {
  color: var(--paper);
}

.ch-wait {
  width: 520px;
  max-width: 100%;
  box-sizing: border-box;
  border: 1.5px dashed rgba(18, 20, 16, 0.3);
  border-radius: 18px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ch-wait__h {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
}

.ch-wait__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.3);
  flex-shrink: 0;
}

.ch-wait__p {
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink-2);
}

.ch--m .ch-wait {
  width: 100%;
  border-radius: 16px;
  padding: 14px;
  gap: 4px;
}

.ch--m .ch-wait__h {
  gap: 8px;
  font-size: 15px;
}

.ch--m .ch-wait__dot {
  width: 8px;
  height: 8px;
  box-shadow: none;
}

.ch--m .ch-wait__p {
  font-size: 12px;
  line-height: 1.45;
}

.ch-rate {
  width: 520px;
  max-width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 2px solid var(--accent);
  border-radius: 18px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ch-rate__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ch-rate__h {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.ch-rate__p {
  font-size: 14px;
  color: var(--ink-2);
}

.ch-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.ch-bad,
.ch-good {
  height: 54px;
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
}

.ch-bad {
  border: 1.5px solid #a3361f;
  background: transparent;
  color: #a3361f;
}

.ch-good {
  border: 0;
  background: var(--forest);
  color: var(--paper);
}

.ch-rate__note {
  font-size: 11px;
  color: var(--muted);
}

.ch--m .ch-rate,
.ch--m .ch-pick,
.ch--m .ch-decide {
  width: 100%;
  border-radius: 16px;
  padding: 14px;
  gap: 10px;
}

.ch--m .ch-rate__head {
  gap: 2px;
}

.ch--m .ch-rate__h {
  font-size: 17px;
  letter-spacing: 0;
}

.ch--m .ch-two {
  gap: 8px;
}

.ch--m .ch-bad,
.ch--m .ch-good {
  height: 48px;
  font-size: 15px;
}

.ch-pick {
  width: 560px;
  max-width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 2px solid var(--ink);
  border-radius: 18px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ch-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ch-chip {
  height: 42px;
  padding: 0 16px;
  border-radius: 999px;
  border: 1.5px solid rgba(18, 20, 16, 0.3);
  background: transparent;
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.ch-chip[aria-pressed='true'] {
  border-color: var(--ink);
  background: var(--ink);
  color: var(--paper);
}

.ch-note {
  box-sizing: border-box;
  padding: 12px 14px;
  background: #f7f3ea;
  border: 0;
  border-radius: 12px;
  line-height: 1.5;
  resize: none;
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--ink);
  outline: none;
}

.ch-note::placeholder {
  color: #8c8e85;
}

.ch-pick__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ch-pick__p {
  font-size: 13px;
  color: var(--muted);
}

.ch-ask-btn {
  height: 48px;
  padding: 0 20px;
  border: 0;
  border-radius: 12px;
  background: var(--forest);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.ch-ask-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ch--m .ch-chips {
  gap: 6px;
}

.ch--m .ch-chip {
  height: 38px;
  padding: 0 12px;
  font-size: 13px;
}

.ch--m .ch-note {
  padding: 10px 12px;
  border-radius: 10px;
  line-height: 1.45;
  font-size: 14px;
}

.ch-decide {
  width: 620px;
  max-width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border: 2px solid var(--ink);
  border-radius: 18px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ch-decide__h {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.ch-decide__opts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.ch-opt {
  text-align: left;
  padding: 18px;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-family: var(--font-display);
  cursor: pointer;
}

.ch-opt--refund {
  border: 1.5px solid #a3361f;
  background: transparent;
}

.ch-opt--go {
  border: 0;
  background: var(--forest);
  color: var(--paper);
}

.ch-opt__h {
  font-size: 17px;
  font-weight: 800;
}

.ch-opt--refund .ch-opt__h {
  color: #a3361f;
}

.ch-opt__p {
  font-size: 13px;
  line-height: 1.45;
  color: var(--ink-2);
}

.ch-opt--go .ch-opt__p {
  color: var(--paper);
  opacity: 0.85;
}

.ch--m .ch-decide__h {
  font-size: 18px;
  letter-spacing: 0;
}

.ch--m .ch-decide__opts {
  grid-template-columns: 1fr;
  gap: 10px;
}

.ch--m .ch-opt {
  padding: 12px 14px;
  border-radius: 12px;
  gap: 2px;
}

.ch--m .ch-opt__h {
  font-size: 15px;
}

.ch--m .ch-opt__p {
  font-size: 12px;
}

.ch-receipt {
  width: 520px;
  max-width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  padding: 22px 24px 30px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}

.ch-receipt__k {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.ch-receipt__amt {
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.ch-receipt__amt--green {
  color: var(--released);
}

.ch-receipt__p {
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink-2);
}

.ch-receipt__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}

.ch-receipt__row span {
  color: var(--muted);
}

.ch-receipt__row strong {
  font-weight: 700;
  text-align: right;
}

.ch-receipt__stamp {
  position: absolute;
  right: 24px;
  top: 26px;
  transform: rotate(9deg);
  border: 3px solid;
  outline: 1.5px solid;
  outline-offset: 3px;
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.14em;
  padding: 4px 9px;
  border-radius: 4px;
}

.ch-receipt__stamp--green {
  color: var(--released);
  border-color: var(--released);
  outline-color: var(--released);
}

.ch-receipt__stamp--red {
  color: #a3361f;
  border-color: #a3361f;
  outline-color: #a3361f;
}

.ch--m .ch-receipt {
  width: 100%;
  border-radius: 14px;
  padding: 16px;
  gap: 8px;
}

.ch--m .ch-receipt__k {
  font-size: 9px;
  letter-spacing: 0.1em;
}

.ch--m .ch-receipt__amt {
  font-size: 32px;
  line-height: normal;
}

.ch--m .ch-receipt__p {
  font-size: 13px;
  line-height: 1.45;
}

.ch--m .ch-receipt__row {
  font-size: 12px;
}

.ch--m .ch-receipt__stamp {
  right: 14px;
  top: 16px;
  border-width: 2.5px;
  outline: 0;
  font-size: 10px;
  letter-spacing: 0.12em;
  padding: 3px 7px;
  border-radius: 3px;
}

.ch :is(button, a, textarea):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}

.ch button:disabled {
  cursor: progress;
}
</style>
