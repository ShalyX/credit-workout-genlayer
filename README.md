# CreditWorkout

CreditWorkout is a reusable GenLayer Intelligent Contract for coordinating lender-approved restructurings of distressed private-credit facilities.

## What it does

1. A facility manager records the borrower's wallet and canonical legal name, principal, due date, cure period, full lender voting weight, quorum, and approval threshold. The manager attests that the name belongs to the wallet; this version does not cryptographically prove that relationship. Keep personal identifying details off-chain; the name field is for an entity's public legal name.
2. Anyone can mark the facility past due after the recorded due date plus cure period. The borrower, manager, or a registered lender may then propose a lower-or-equal principal and a future revised due date, with a rationale and borrower-update URL.
3. GenLayer validators independently retrieve and assess the cited update. The retrieved text must explicitly contain the registered borrower legal name before model review; validators then agree on the structured outcome, confidence band, and SHA-256 fingerprint of the normalized source. Only a `supported` result with `high` confidence opens a vote. `unclear`, `unsupported`, malformed output, or source failure cannot open a ballot.
4. Registered lenders vote with pre-registered weights. Votes may be changed while the ballot is open; the contract removes the previous weight before recording the new vote.
5. After the voting window, the contract applies the amended principal and due date only if the fixed-weight quorum and approval threshold pass and the facility revision has not changed. Recovery during voting immediately stales and closes the proposal.

This is a workout-governance primitive, not a generic evidence-verification service. Consensus assessment informs a creditor vote; it does not replace it. The contract does not hold or transfer loan funds, verify off-chain payments, establish legal default, or give legal or investment advice. The manager-attested `record_recovery` method and borrower-name-to-wallet association are explicit trust boundaries. A production pool should connect this state machine to an authoritative payment/servicing integration or require a separate on-chain payment attestation process.

## Current scope

- One principal balance and one revised due date per facility; no interest accrual, installment schedule, seniority waterfall, tokenized lender-position transfer, or asset custody.
- Lender weights are fixed by the manager at setup and must sum to the declared total before a facility can enter workout.
- A workout proposal may reduce principal, never increase it.
- A new proposal can be created after a rejected/no-quorum/stale workout or after a later default following an approved restructure.
- Borrower disclosures are fetched at review time. For production, use immutable/versioned evidence URLs; if validators fetch different versions, consensus should fail closed and the review can be retried against a stable snapshot.

## Test

Python 3.12+ and `genlayer-test` are required. Install `requirements.txt`, then run:

```powershell
python -m pytest tests/direct -q
```

The direct suite uses mocked web/LLM responses and tests the contract in GenLayer's in-memory VM. It is not a StudioNet deployment or a live consensus test.

## Research context and realistic scenarios

The adversarial fixtures in [`docs/adversarial-scenarios.md`](docs/adversarial-scenarios.md) model recurring private-credit workout problems: disputed covenant updates, related-party lending disclosures, partial recovery during a vote, lender abstention/no-quorum, and a subsequent missed payment after restructuring. Public governance reports are context for scenario design, not proof that this contract can determine legal breach or predict recovery.

## GenLayer design

Contract state, cure windows, voting weights, quorum, approval math, and application of amended terms are deterministic. External borrower updates and qualitative recovery-support assessment run in a non-deterministic block; storage changes occur only after the accepted consensus result. See the official [Intelligent Contract overview](https://docs.genlayer.com/developers/intelligent-contracts/first-intelligent-contract), [storage guide](https://docs.genlayer.com/developers/intelligent-contracts/storage), [equivalence-principle guide](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle), and [testing guide](https://docs.genlayer.com/developers/intelligent-contracts/testing).
