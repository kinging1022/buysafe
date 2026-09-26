// Used only by scripts/prerender.js at build time to render static HTML for
// the landing route. Anything rendered here must avoid browser APIs outside
// onMounted. Pinia is installed so the landing nav can read the auth store, but
// it renders signed out (the user is only fetched in onMounted).
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import { renderToString } from 'vue/server-renderer'
import { createRouter, createMemoryHistory } from 'vue-router'

import App from './App.vue'
import { routes } from './router/routes'

export async function render(url) {
  const app = createSSRApp(App)
  const router = createRouter({ history: createMemoryHistory(), routes })
  app.use(createPinia())
  app.use(router)
  await router.push(url)
  await router.isReady()
  return renderToString(app)
}
