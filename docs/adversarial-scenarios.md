# Adversarial and real-world scenario set

These cases are designed to test a workout state machine against the kinds of events discussed in public private-credit restructurings. They are not assertions that a borrower breached a particular legal agreement. Public reports can be incomplete, contested, or later updated.

## Reference situations

- **Related-party lending disclosure:** Goldfinch governance discussion of the Lend East pool reported a disputed related-party/intercompany loan and subsequent workout discussion: [Lend East pool update](https://gov.goldfinch.finance/t/update-on-lend-east-pool/1957).
- **Facility-agreement and restructuring pressure:** A Goldfinch governance update on Tugende described a related-company loan and a restructuring context: [Tugende facility update](https://gov.goldfinch.finance/t/update-on-the-tugende-kenya-facility/1809).
- **Impairment/default distinction:** Maple's documentation distinguishes a potential default/impairment state from a final economic recovery outcome: [Syrup defaults and impairments](https://docs.maple.finance/legal/syrupusdc-and-syrupusdt-defaults-and-impairments).

These sources motivate tests for disclosure quality, cure/workout timing, creditor coordination, and the gap between a flagged concern and a realized loss. The contract does not encode these entities' terms or resolve their historical facts.

## Executable scenarios

The direct suite covers the following paths:

1. **Supported recovery plan → creditor-approved extension:** consensus assessment is `supported/high`; 100% of lender weight votes yes; after the ballot ends, revised terms apply.
2. **Vague recovery case:** assessment is `unclear/medium`; no ballot opens and lender votes revert.
3. **Unavailable source:** HTTP 503 produces `source_failure/low`; no ballot opens.
4. **Cure period still running:** a past-due transition is rejected before the due date plus grace period.
5. **Partial recovery during voting:** the manager records a recovery; the active proposal becomes stale immediately, voting closes, and the changed balance is preserved.
6. **Lender vote changed:** a lender switches from yes to no; its weight moves, rather than appearing in both tallies.
7. **No quorum:** a yes vote below the configured participation threshold cannot apply terms.
8. **Quorum with rejection:** full lender participation but insufficient yes share rejects the proposal without changing the existing debt terms.
9. **Subsequent default:** an approved restructure can later pass its new due date and re-enter the cure/workout flow.
10. **Adversarial proposal terms:** principal increases and already-expired revised dates are rejected.
11. **Validator source drift:** the validator independently re-fetches the page; even if its qualitative outcome matches the leader's, a changed source fingerprint rejects that leader result.
12. **Borrower identity mismatch:** a recovery-like source that omits the registered legal name is blocked before model review, even when a mocked model response says `supported/high`.

## Live StudioNet checks

On 2026-10-24, the deployed contract was exercised with two public-source case-study fixtures. The deployed source was read back from StudioNet and matched `contracts/credit_workout.py` byte-for-byte after newline normalization. The direct test suite passed 18 tests.

1. **Public terms matched:** Getty Images RSA reporting states that $580 million in new notes mature in April 2032. A synthetic Getty-named facility used those terms and the cited public case update. Consensus returned `MAJORITY_AGREE`; the stored review was `supported/high`. A 100-weight test lender voted yes; after the voting window, the proposal finalized as `approved` and the facility as `restructured`.
2. **Borrower-name mismatch:** the same Getty source was attached to a fixture registered as Acme Flight Systems. Consensus returned `MAJORITY_AGREE`, but the contract stored `unclear/low` and `review_blocked`, with no ballot opened.

These are live consensus and state-transition tests using public, borrower-linked restructuring information, but the facilities, borrower addresses, and lender roster are synthetic. They do not establish an actual Getty loan, creditor identity, legal default, or creditor decision. The contract does not verify the manager's off-chain name-to-wallet attestation or custody/transfer loan assets. See the [SEC-filed restructuring agreement](https://www.sec.gov/Archives/edgar/data/1898496/000121390026111193/ea030922501ex99-1.htm) for the public terms used in the case study.
