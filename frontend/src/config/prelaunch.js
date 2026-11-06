// Head tags for the pre-launch page (design/prelaunch.reference.html). No
// browser or import.meta.env access here: vite.config.js imports it too.
export const PRELAUNCH_META = {
  title: 'buysafe · Buy second-hand without sending money first',
  description:
    'buysafe holds your money until you’ve met the seller, checked the item and said yes. Coming soon to every state in Nigeria. Join the waitlist.',
  ogTitle: 'buysafe · Money that waits',
  ogDescription:
    'Buy and sell used things anywhere in Nigeria. Your payment is held until you’ve seen the item. Join the waitlist.',
  // App.vue leaves out its "Skip to content" link; this page has its own.
  ownSkipLink: true,
  // Hash links land flush with the top, as in the reference (no sticky nav).
  hashOffset: 0,
}

// TODO: og:image. Add a 1200×630 share image and set OG_IMAGE in config/landing.js.
