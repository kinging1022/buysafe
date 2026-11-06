import feeData from './fees.generated.json' with { type: 'json' }
import { naira } from '../utils/format.js'

// Values the landing page computes or repeats. Placeholders stay in
// [BRACKETS] exactly as in design/landing-desktop.reference.html until the
// real details are known.

export const VENDOR_COMMISSION_PERCENT = 10 // TODO confirm

export const PAYMENT_PARTNER = '[PAYMENT PARTNER]'
export const WHATSAPP_NUMBER = '[NUMBER]'
export const CONTACT_EMAIL = '[EMAIL]'
export const BUSINESS_NAME = '[REGISTERED BUSINESS NAME]'

export { naira }

// The fee tiers and worked examples come from the backend's calculate_fee(),
// exported by `python manage.py export_fee_schedule` (a backend test fails if
// this file goes stale). No fee maths happens in the frontend.
export const FEE_TIERS = feeData.tiers

// Fees section: ₦50,000 sale.
export const FEE_EXAMPLE = feeData.examples.fees_section

// How it works, step 04: the fridge.
export const FRIDGE_EXAMPLE = feeData.examples.fridge

// Vendor payout card: the sofa. The vendor commission is its own TODO and
// still comes off here.
export const SOFA_EXAMPLE = (() => {
  const { price, fee, rate_label: rate, payout } = feeData.examples.sofa
  const commission = (price * VENDOR_COMMISSION_PERCENT) / 100
  return { sale: price, fee, rate, commission, sellerReceives: payout - commission }
})()

export const PAGE_META = {
  title: 'buysafe — Buy and sell used items safely.',
  description:
    'Buy and sell pre-owned items safely anywhere in Nigeria, without the “send money first” wahala. Meet, check the item and confirm before the seller gets paid.',
}

// TODO: production origin (og:url) and a 1200×630 share image (og:image).
export const SITE_URL = null
export const OG_IMAGE = null
