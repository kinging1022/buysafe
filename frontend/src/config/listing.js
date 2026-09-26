// Listing vocabulary shared by browse and Post an item.
// Condition keys match the backend (Listing.Condition); meanings are from
// design/sell-5-condition-dropdown-open-desktop.reference.html.
export const CONDITIONS = [
  { key: 'brand_new', label: 'Brand new', meaning: 'Never used, still sealed or in its box.' },
  { key: 'like_new', label: 'Like new', meaning: 'Used a few times. No visible marks.' },
  { key: 'good', label: 'Good', meaning: 'Works well. Normal signs of use.' },
  { key: 'fair', label: 'Fair', meaning: 'Works, but has clear wear or small faults.' },
  { key: 'for_parts', label: 'For parts', meaning: 'Doesn’t work properly. Sold for repair or parts.' },
]

export const conditionLabel = (key) => CONDITIONS.find((c) => c.key === key)?.label ?? ''

export const SORTS = [
  { key: 'newest', label: 'Newest first', short: 'Newest' },
  { key: 'price_asc', label: 'Price: low to high', short: 'Lowest price' },
  { key: 'price_desc', label: 'Price: high to low', short: 'Highest price' },
]

// Shorter category names for the mobile chips and headline (browse-*-mobile).
// Categories come from the API; anything not listed here uses its full name.
const SHORT_CATEGORY = {
  'phones-tablets': 'Phones',
  'laptops-computers': 'Laptops',
  'home-appliances': 'Appliances',
  'tvs-audio': 'TVs',
  'generators-power': 'Generators',
  'sports-fitness': 'Sports',
}

export const shortCategory = (category) => SHORT_CATEGORY[category.slug] ?? category.label
