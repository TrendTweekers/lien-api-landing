/**
 * Billing configuration
 * Controls which billing options are available and how checkout works
 */
export interface BillingConfig {
  supportsMonthly: boolean;
  checkoutType: "payment_link" | "stripe_checkout" | "custom";
}

/**
 * Current billing configuration
 * When using Payment Links, monthly is always supported (no Stripe keys needed)
 */
export const billingConfig: BillingConfig = {
  supportsMonthly: true,
  checkoutType: "payment_link",
};

