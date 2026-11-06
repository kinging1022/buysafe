// Routes the signed-in pages link to. Change number is still a TODO placeholder.
export const ROUTES = {
  browse: '/listings',
  // Deals & messages: every chat belongs to a deal (there's no separate inbox).
  deals: '/deals',
  notifications: '/notifications',
  sell: '/sell',
  payout: '/profile/payout',
  changePhone: '/profile/phone',
}

export const listingLinks = (id) => ({
  view: `/listings/${id}`,
  edit: `/sell/${id}/edit`,
})

export const dealLinks = (id) => ({
  view: `/deals/${id}`,
  record: `/deals/${id}/record`,
})

// TODO: the review SLA. Keep the placeholder until it's confirmed.
export const REVIEW_SLA = '[X HOURS]'
