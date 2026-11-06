<script setup>
// The pre-launch page, served at / while VITE_PRELAUNCH=true (router/routes.js).
// Copy and layout from design/prelaunch.reference.html; styles in
// styles/prelaunch.css. Prerendered at build time, so no browser APIs in setup.
import '@/styles/prelaunch.css'
import { ref } from 'vue'
import WaitlistForm from '@/components/prelaunch/WaitlistForm.vue'

// The photo is optional: if src/assets/prelaunch/ps5.jpg is missing or fails to
// load, the photo well shows the text fallback. A glob (not a plain import)
// so the build works without the file; it's still fingerprinted when present.
const ps5Url = Object.values(
  import.meta.glob('@/assets/prelaunch/ps5.jpg', { eager: true, query: '?url', import: 'default' }),
)[0]
const photoFailed = ref(!ps5Url)

const heroForm = ref(null)

// Footer contact links; each is hidden while its value is empty.
const contactEmail = import.meta.env.VITE_CONTACT_EMAIL || ''
const instagramHandle = (import.meta.env.VITE_INSTAGRAM_HANDLE || '').replace(/^@/, '')
</script>

<template>
  <div class="prelaunch">
    <a class="skip" href="#join">Skip to the waitlist</a>

    <header class="nav">
      <div class="wrap">
        <a class="logo" href="#" aria-label="buysafe home">buysafe<span>.</span></a>
        <a class="nav-cta" href="#join">Join the waitlist</a>
      </div>
    </header>

    <main>
      <div class="hero">
        <p class="eyebrow">Coming soon to all 36 states and the FCT</p>
        <h1>Money that <span class="it">waits.</span></h1>
        <p class="lede">Buy anything second-hand, anywhere in Nigeria. We hold your money until you’ve met the seller, checked the item and said yes.</p>

        <WaitlistForm id="join" ref="heroForm" />

        <div class="stage" aria-label="Example deal">
          <div class="callout l">
            <small>Held in escrow</small>
            <b class="num">₦280,000</b>
            <span class="rule"></span>
          </div>
          <div class="deal">
            <div class="photo">
              <img v-if="!photoFailed" :src="ps5Url" alt="PlayStation 5 Slim listed for sale" width="824" height="618" loading="eager" fetchpriority="high" @error="photoFailed = true">
              <span v-else class="ph">PlayStation 5 Slim</span>
            </div>
            <div class="deal-body">
              <div class="deal-top">
                <div>
                  <b class="deal-title">PlayStation 5 Slim</b>
                  <p>Used 1 year · Ikeja, Lagos</p>
                </div>
                <span class="pill num">₦280,000 held</span>
              </div>
              <ol class="track" aria-label="Where the money is">
                <li class="on"><i></i>Paid</li>
                <li class="now"><i></i>Held</li>
                <li><i></i>Checked</li>
                <li><i></i>Released</li>
              </ol>
            </div>
          </div>
          <div class="callout r">
            <span class="rule"></span>
            <em>Seller is paid</em>
            <small>the moment you say yes</small>
          </div>
        </div>

        <div class="trust">
          <span>Every user is phone-verified</span>
          <span>Every message stays in the app</span>
          <span>Refunds go back to the account you paid from</span>
        </div>
      </div>

      <section aria-labelledby="old-h">
        <div class="wrap old">
          <div>
            <p class="kicker">Why we’re building this</p>
            <h2 id="old-h">Somebody always has to go first.</h2>
            <span class="it">And sometimes they lose.</span>
          </div>
          <div class="old-cols">
            <div><b>If you’re buying</b><p>You send the transfer, they say “received”. Then the photos stop matching, or the number stops going through.</p></div>
            <div><b>If you’re selling</b><p>You clean it, pack it, cross the city to meet, and the buyer is “on the way” for two hours before going quiet.</p></div>
          </div>
        </div>
      </section>

      <section class="how" aria-labelledby="how-h">
        <div class="wrap">
          <p class="kicker">How it works</p>
          <h2 id="how-h">Nobody pays first. The money waits <span class="it">in the middle.</span></h2>
          <ol class="steps">
            <li><b>Pay into escrow</b><p>Send a bank transfer to an account number made just for your deal. The seller sees the money is there. Nobody can touch it.</p></li>
            <li><b>See it, live</b><p>The seller records a live video of the item in the app. Camera only, no gallery. You rate it, or ask to see more.</p></li>
            <li><b>Meet and check</b><p>Agree on a time and a public place in the app chat. Switch it on, look it over.</p></li>
            <li><b>Say yes</b><p>Confirm with the item in your hands and the seller is paid straight away.</p></li>
          </ol>
        </div>
      </section>

      <section aria-labelledby="wrong-h">
        <div class="wrap">
          <p class="kicker">If it goes wrong</p>
          <h2 id="wrong-h">We planned for the bad days first.</h2>
          <div class="wrong-grid">
            <div><b>The seller doesn’t send a video in time.</b><p>The deal is cancelled and your money goes back to the account you paid from, in full.</p></div>
            <div><b>The video doesn’t look right.</b><p>Ask for another one and say exactly what to show. After three, you can cancel for a full refund.</p></div>
            <div><b>The item isn’t what you saw.</b><p>Don’t confirm. Report it in the app. Your money stays held while a real person reviews the deal.</p></div>
          </div>
        </div>
      </section>

      <section class="fees" aria-labelledby="fees-h">
        <div class="wrap fees-grid">
          <div>
            <p class="kicker">Fees</p>
            <h2 id="fees-h">Free to buy. Sellers pay only when it sells.</h2>
            <p class="sub">The fee comes out of the payout, and you see the exact amount before you post.</p>
          </div>
          <div>
            <div class="table num">
              <div class="row buyer"><span>Buyers</span><b>₦0</b></div>
              <div class="row"><span>Items under ₦10,000</span><b>₦1,500 flat</b></div>
              <div class="row"><span>₦10,000 to ₦19,999</span><b>15%</b></div>
              <div class="row"><span>₦20,000 and above</span><b>10%</b></div>
            </div>
            <p class="fine">Minimum listing price ₦2,000.</p>
          </div>
        </div>
      </section>

      <section class="vendors" aria-labelledby="v-h">
        <div class="wrap vendors-in">
          <div>
            <p class="kicker">Run a declutter page?</p>
            <h2 id="v-h">Stop chasing transfers. <span class="it">Bring it here.</span></h2>
            <p class="sub">Every client’s items in one place, and buyers who have already paid before you leave the house.</p>
          </div>
          <a class="dark-link" href="#join" @click="heroForm?.selectRole('vendor')">Join as a vendor</a>
        </div>
      </section>

      <section class="final" aria-labelledby="final-h">
        <div class="wrap">
          <h2 id="final-h">Be first when we open <span class="it">in your state.</span></h2>
          <p class="sub">One text when buysafe is live near you. Nothing else.</p>
          <WaitlistForm id="join-2" />
        </div>
      </section>
    </main>

    <footer>
      <div class="wrap">
        <span>© 2026 buysafe</span>
        <nav v-if="contactEmail || instagramHandle" aria-label="Contact">
          <a v-if="contactEmail" :href="`mailto:${contactEmail}`">{{ contactEmail }}</a>
          <a v-if="instagramHandle" :href="`https://instagram.com/${instagramHandle}`" rel="noopener">Instagram</a>
        </nav>
      </div>
    </footer>
  </div>
</template>
