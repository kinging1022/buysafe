import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'
import { applyHead } from './head'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    // Land below the sticky nav (its height is the --nav-h CSS variable),
    // unless the route sets meta.hashOffset.
    if (to.hash) {
      const navH = to.meta.hashOffset ?? parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-h'))
      const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
      return { el: to.hash, top: navH || 0, behavior: smooth ? 'smooth' : 'auto' }
    }
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  if (!to.meta.guestOnly && !to.meta.requiresAuth) return
  const auth = useAuthStore()
  await auth.ensureLoaded()
  if (to.meta.requiresAuth) {
    if (!auth.user) return { path: '/login', query: { redirect: to.fullPath } }
    return
  }
  if (auth.user) return '/'
  if (to.meta.requiresPending && !auth.pendingPhone) return { path: '/signup', query: to.query }
})

router.afterEach((to) => applyHead(to.meta))

export default router
