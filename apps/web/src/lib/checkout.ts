import { PRICE_USD } from "@tirekick/shared";

/**
 * Checkout configuration.
 *
 * A Stripe payment link is a URL, so there is no secret to hold and no server
 * route to write - which is the right amount of machinery for a single-product
 * checkout at this stage.
 *
 * ---------------------------------------------------------------------------
 * THIS FILE DOES NOT CHARGE ANYBODY, AND USED TO SAY IT DID
 * ---------------------------------------------------------------------------
 *
 * The landing page carried a comment reading "the number comes from checkout.ts,
 * which is what actually charges it". It does not. `paymentLink` appends
 * `client_reference_id` and nothing else; the amount lives in the payment link's
 * own configuration at Stripe, outside this repository. `PRICE_USD` could be
 * changed to 30 here, every gate in the repository would stay green, every page
 * would read $30, and the buyer would still be billed whatever Stripe holds.
 * Nothing in this repository can read that amount, and nothing here checks it.
 * That is a fact about the boundary, not a gap somebody forgot to close.
 *
 * What can be checked is a *declaration*. A deployment that sets
 * NEXT_PUBLIC_STRIPE_PAYMENT_LINK must also set NEXT_PUBLIC_STRIPE_PRICE_USD to
 * the amount it configured over there, and `checkoutState` refuses to hand back
 * a payable href unless that declaration matches the price the pages print. It
 * catches the mistake that is actually made - the constant moved, or the Stripe
 * product was edited, and the other side was forgotten. It cannot catch a
 * deployment that declares one amount and configures another, because that is
 * the same unreadable boundary again, so the checkout page also tells the buyer
 * to read the amount on the payment page before confirming. A person looking at
 * the Stripe page is the only reader in this system who can see both numbers.
 *
 * The other behaviour here is what happens when it is NOT configured. An unset
 * link must produce a visibly disabled state that says so, never a dead href
 * that looks live and silently fails. A checkout that appears to work and does
 * not is worse than one that admits it is not ready - and a checkout whose
 * deployment cannot say what it charges is in that same category.
 */

export { PRICE_USD };

/** Where a caller stands with the checkout, and why it is not open if it is not. */
export type CheckoutState =
  | { kind: "ready"; href: string }
  | { kind: "no_link" }
  | { kind: "amount_undeclared" }
  | { kind: "amount_disagrees"; declared: string };

export function paymentLink(inspectionId: string): string | null {
  const base = process.env.NEXT_PUBLIC_STRIPE_PAYMENT_LINK;
  if (!base) return null;
  // Stripe passes client_reference_id straight through to the webhook, which is
  // how a completed payment is matched back to an inspection. It is the only
  // parameter we add: no amount is sent, so no amount can be asserted.
  const url = new URL(base);
  url.searchParams.set("client_reference_id", inspectionId);
  return url.toString();
}

export function checkoutState(inspectionId: string): CheckoutState {
  const href = paymentLink(inspectionId);
  if (href === null) return { kind: "no_link" };

  const declared = process.env.NEXT_PUBLIC_STRIPE_PRICE_USD;
  if (declared === undefined || declared.trim() === "") {
    return { kind: "amount_undeclared" };
  }
  // A non-numeric declaration is a disagreement, not a missing one. Treating an
  // unparseable value as "no opinion" would let a typo open the button.
  if (Number(declared) !== PRICE_USD) return { kind: "amount_disagrees", declared };

  return { kind: "ready", href };
}
