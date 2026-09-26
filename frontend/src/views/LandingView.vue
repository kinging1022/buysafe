<script setup>
// Keep this route light: no stores, no app-only components.
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
</script>

<template>
  <div class="landing">
    <LandingNav />
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
