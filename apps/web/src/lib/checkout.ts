/**
 * Checkout configuration.
 *
 * A Stripe payment link is a URL, so there is no secret to hold and no server
 * route to write - which is the right amount of machinery for a single-product
 * checkout at this stage.
 *
 * The important behaviour here is what happens when it is NOT configured. An
 * unset link must produce a visibly disabled button that says so, never a dead
 * href that looks live and silently fails. A checkout that appears to work and
 * does not is worse than one that admits it is not ready.
 */

export const PRICE_USD = 25;

export function paymentLink(inspectionId: string): string | null {
  const base = process.env.NEXT_PUBLIC_STRIPE_PAYMENT_LINK;
  if (!base) return null;
  // Stripe passes client_reference_id straight through to the webhook, which is
  // how a completed payment is matched back to an inspection.
  const url = new URL(base);
  url.searchParams.set("client_reference_id", inspectionId);
  return url.toString();
}

export function checkoutConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_STRIPE_PAYMENT_LINK);
}
