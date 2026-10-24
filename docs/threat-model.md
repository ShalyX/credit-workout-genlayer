# Threat model

## Assets and invariants

- A workout vote must apply only to the exact facility revision reviewed by lenders.
- Lender voting weight must be fixed before distress and sum to the declared pool weight.
- A borrower update that is unavailable, malformed, ambiguous, unsupported, or low-confidence must not open a lender ballot.
- A lender can contribute its weight once per ballot; changing a vote replaces rather than duplicates it.
- No amended terms are applied before the ballot closes or without quorum and the required approval fraction.
- A recovery or other facility-state change invalidates an open proposal immediately.

## Adversaries and failure modes

| Threat | Control | Remaining limitation |
| --- | --- | --- |
| Borrower submits unrelated, vague, or misleading recovery evidence | The source must explicitly contain the facility's registered borrower legal name; independent validators then assess the cited URL, and only a high-confidence `supported` result opens voting | Exact-name matching can reject legitimate aliases or trade names; source identity is not proof of cash, collateral value, or repayment, and lenders retain the decision |
| Source endpoint is unavailable or changes between validators | Source failure blocks voting; validators compare the normalized source fingerprint | Mutable URLs can prevent consensus; use immutable documents or versioned endpoints |
| Proposal tries to increase principal or use an expired date | Deterministic bounds reject both | Principal-only model does not encode fees, interest, covenants, or legal priority |
| Manager understates/overstates lender weights | Declared total is fixed at facility creation; registration must exactly fill it before distress | Manager chooses the initial roster and weights; token ownership/transfer is not verified here |
| One lender votes repeatedly to inflate weight | One mapping entry per lender/proposal; a changed vote first removes the prior tally | Lender identity is an address; no delegation or wallet recovery flow |
| Recovery occurs after lenders begin voting | Manager recovery increments revision, marks the proposal stale, and closes voting immediately | `record_recovery` is manager-attested rather than proof of an actual payment |
| Ballot has low participation or fails approval | Fixed total weight sets quorum; yes weight is compared to cast weight for the approval threshold | The governing agreement may require a different denominator or special lender classes |
| Proposal identifier or facility identifier is replayed | Identifiers are permanently reserved; state transitions and proposal status gate calls | IDs are strings and not cryptographic content commitments |
| A consensus assessment is uncertain or malformed | Only matching high-confidence supported outcomes open a vote; invalid model output becomes `unclear` | This contract does not replace legal counsel, a servicer, or credit underwriting |

## Trust boundaries

1. The facility manager is trusted to create an accurate lender roster, attest that the canonical borrower name belongs to the recorded wallet, and report recoveries truthfully. This release does not cryptographically bind a legal entity to its wallet.
2. The cited borrower update is treated as untrusted input. Embedded instructions do not override the review prompt.
3. GenLayer consensus establishes agreement under the contract's review criteria, not objective truth or legal enforceability.
4. Lenders remain responsible for whether the approved workout is permitted by their facility agreement and applicable law.

## Out of scope

The current contract does not custody assets, execute collections, calculate interest, value collateral, adjudicate contract clauses as a court, or bind off-chain lenders who have not registered on-chain. These are explicit exclusions, not completed product capabilities.
