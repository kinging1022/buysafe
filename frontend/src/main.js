import './styles/landing-tokens.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// Wait for the first route so a prerendered page is swapped for identical
// markup, instead of flashing empty while the route resolves.
router.isReady().then(() => app.mount('#app'))
