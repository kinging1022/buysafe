<script setup>
// Keep this route light: it's prerendered signed out, and app-only code
// (AppHeader) loads only once we know the visitor is signed in.
import { shallowRef, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import LandingNav from '@/components/landing/LandingNav.vue'
import HeroSection from '@/components/landing/HeroSection.vue'
import CategoryStrip from '@/components/landing/CategoryStrip.vue'
import OldWaySection from '@/components/landing/OldWaySection.vue'
import HowItWorksSection from '@/components/landing/HowItWorksSection.vue'
import GoesWrongSection from '@/components/landing/GoesWrongSection.vue'
import MeetSafelySection from '@/components/landing/MeetSafelySection.vue'
import VendorsSection from '@/components/landing/VendorsSection.vue'
import FeesSection from '@/components/landing/FeesSection.vue'
import FounderNote from '@/components/landing/FounderNote.vue'
import FaqSection from '@/components/landing/FaqSection.vue'
import FinalCta from '@/components/landing/FinalCta.vue'

// Signed in: the same header as every other page (notifications count,
// the mobile bell and panel). Signed out: the landing nav with its section
// links. The landing nav stays up until AppHeader has loaded, so the bar
// never goes empty.
const auth = useAuthStore()
const AppHeader = shallowRef(null)
watch(
  () => auth.user,
  (user) => {
    if (user && !AppHeader.value) {
      import('@/components/account/AppHeader.vue').then((m) => (AppHeader.value = m.default))
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="landing">
    <component :is="AppHeader" v-if="auth.user && AppHeader" sticky />
    <LandingNav v-else />
    <main id="main">
      <HeroSection />
      <CategoryStrip />
      <OldWaySection />
      <HowItWorksSection />
      <GoesWrongSection />
      <MeetSafelySection />
      <VendorsSection />
      <FeesSection />
      <FounderNote />
      <FaqSection />
    </main>
    <!-- Final CTA + page footer; outside <main> so <footer> is the page footer. -->
    <FinalCta />
  </div>
</template>

<style scoped>
/* Clips the decorative rings sideways without breaking the sticky nav. */
.landing {
  overflow-x: clip;
}
</style>
