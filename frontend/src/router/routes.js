// Route table, kept free of browser APIs so the prerender step
// (src/entry-server.js) can import it.
import LandingView from '@/views/LandingView.vue'
import PrelaunchView from '@/views/PrelaunchView.vue'
import { PAGE_META } from '@/config/landing'
import { PRELAUNCH_META } from '@/config/prelaunch'

// The go-live switch: VITE_PRELAUNCH=true serves only the pre-launch waitlist
// page (see README, "Pre-launch mode").
export const PRELAUNCH = import.meta.env.VITE_PRELAUNCH === 'true'

// TODO: /vendors/apply, /terms and /privacy are linked from the landing page but
// don't exist yet; they fall through to the not-found route. /profile/phone
// is a placeholder.
const siteRoutes = [
  {
    path: '/',
    name: 'landing',
    // Eager: this is the entry route, and prerendering needs it synchronously.
    component: LandingView,
    meta: PAGE_META,
  },
  // Auth: lazy-loaded so none of it ships with the landing page.
  // guestOnly: signed-in users are sent to /. requiresPending: /verify needs a
  // phone waiting for its code, otherwise it goes back to /signup.
  {
    path: '/signup',
    name: 'signup',
    component: () => import('@/views/auth/SignUpView.vue'),
    meta: { title: 'Create account', guestOnly: true },
  },
  {
    path: '/verify',
    name: 'verify',
    component: () => import('@/views/auth/VerifyPhoneView.vue'),
    meta: { title: 'Verify your phone', guestOnly: true, requiresPending: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: 'Log in', guestOnly: true },
  },
  {
    // Open to everyone: signed-in users reach it from "Forgot it?" on /profile/password.
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/views/auth/ResetPasswordView.vue'),
    meta: { title: 'Reset password' },
  },
  // Account: requiresAuth sends signed-out users to /login and back.
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/account/ProfileView.vue'),
    meta: { title: 'Your profile', requiresAuth: true },
  },
  {
    path: '/profile/edit',
    name: 'profile-edit',
    component: () => import('@/views/account/EditProfileView.vue'),
    meta: { title: 'Edit profile', requiresAuth: true },
  },
  {
    path: '/profile/password',
    name: 'profile-password',
    component: () => import('@/views/account/ChangePasswordView.vue'),
    meta: { title: 'Change password', requiresAuth: true },
  },
  {
    // The mobile bell's panel, and a page on desktop. The count is polled
    // (stores/notifications.js). TODO: pushed over Django Channels with chat.
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/views/account/NotificationsView.vue'),
    meta: { title: 'Notifications', requiresAuth: true },
  },
  {
    // Where sellers are paid (design/payout-*). Linked from the sell form and
    // the owner's listing page when it's missing.
    path: '/profile/payout',
    name: 'profile-payout',
    component: () => import('@/views/account/PayoutView.vue'),
    meta: { title: 'Payout account', requiresAuth: true },
  },
  // Deals & messages. Every chat belongs to one deal; there's no separate inbox.
  {
    path: '/deals',
    name: 'deals',
    component: () => import('@/views/deals/DealsView.vue'),
    meta: { title: 'Deals & messages', requiresAuth: true },
  },
  {
    // The view sets the title once the deal loads.
    path: '/deals/:id(\\d+)',
    name: 'deal',
    component: () => import('@/views/deals/DealView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // The seller's live-video camera (phones; desktop shows a QR code to it).
    path: '/deals/:id(\\d+)/record',
    name: 'deal-record',
    component: () => import('@/views/deals/RecordView.vue'),
    meta: { title: 'Record your live video', requiresAuth: true },
  },
  // TODO placeholders until these pages are built.
  {
    // Will reuse the OTP flow (purpose change_phone).
    path: '/profile/phone',
    name: 'profile-phone',
    component: () => import('@/views/account/PlaceholderView.vue'),
    meta: { title: 'Change number', requiresAuth: true },
    props: { heading: 'Change number', back: '/profile/edit', backLabel: 'Back to edit profile' },
  },
  // Browse is public; posting needs a signed-in, phone-verified account.
  {
    path: '/listings',
    name: 'listings',
    component: () => import('@/views/listings/ListingsView.vue'),
    meta: { title: 'Browse' },
  },
  {
    // Public. The buyer page, or the owner's page (ListingOwnerView) for the
    // seller; ?as=buyer lets the seller preview the buyer page. The view sets
    // the title ("{title} · buysafe") once the listing loads.
    path: '/listings/:id(\\d+)',
    name: 'listing',
    component: () => import('@/views/listings/ListingDetailView.vue'),
  },
  {
    path: '/sell',
    name: 'sell',
    component: () => import('@/views/sell/CreateListingView.vue'),
    meta: { title: 'Post an item', requiresAuth: true },
  },
  {
    path: '/sell/:id(\\d+)/edit',
    name: 'sell-edit',
    component: () => import('@/views/sell/CreateListingView.vue'),
    meta: { title: 'Edit your item', requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: 'Page not found' },
  },
]

// Staff auth pages stay reachable in pre-launch mode; Django admin is separate.
const PRELAUNCH_OPEN_ROUTES = ['login', 'reset-password']

const prelaunchRoutes = [
  {
    path: '/',
    name: 'prelaunch',
    // Eager, like the landing route: it's the prerendered entry page.
    component: PrelaunchView,
    meta: PRELAUNCH_META,
  },
  ...siteRoutes.filter((r) => PRELAUNCH_OPEN_ROUTES.includes(r.name)),
  {
    // Everything else lands on the waitlist, keeping ?utm_… for attribution.
    path: '/:pathMatch(.*)*',
    redirect: (to) => ({ path: '/', query: to.query, hash: to.hash }),
  },
]

export const buildRoutes = (prelaunch = PRELAUNCH) => (prelaunch ? prelaunchRoutes : siteRoutes)

export const routes = buildRoutes()
