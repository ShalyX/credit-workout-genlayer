import time


CONTRACT = "contracts/credit_workout.py"
BORROWER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
LENDER_A = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
LENDER_B = "0xcccccccccccccccccccccccccccccccccccccccc"


def deploy(direct_deploy):
    return direct_deploy(CONTRACT, sdk_version="v0.2.16")


def new_facility(contract, direct_vm, direct_alice, direct_bob, facility_id="loan-1"):
    direct_vm.sender = direct_alice
    contract.create_facility(
        facility_id,
        direct_bob,
        "Acme Borrower Ltd",
        100_000,
        int(time.time()) + 60,
        60,
        600,
        7500,
        6000,
        10000,
    )
    contract.register_lender(facility_id, LENDER_A, 6000)
    contract.register_lender(facility_id, LENDER_B, 4000)


def mark_overdue(contract, direct_vm, direct_bob):
    facility = contract.get_facility("loan-1")
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(facility["due_at"] + facility["grace_seconds"] + 1)))
    direct_vm.sender = direct_bob
    contract.mark_past_due("loan-1")


def propose(
    contract, direct_vm, direct_bob, proposal_id="workout-1", principal=90000,
    due_at=None, outcome="supported", confidence="high", source_status=200,
    review_response=None, source_body=None,
):
    direct_vm.sender = direct_bob
    contract.propose_workout(
        "loan-1",
        proposal_id,
        principal,
        due_at or int(time.time()) + 86400,
        "Extend 30 days; borrower forecasts recovery from contracted receivables.",
        "https://evidence.example/borrower-update",
    )
    direct_vm.mock_web(
        r"(?s).*evidence\.example/borrower-update.*",
        {
            "status": source_status,
            "body": source_body if source_body is not None else (
                "Acme Borrower Ltd update: contracted receivables are scheduled to settle within 30 days."
                if 200 <= source_status < 300
                else ""
            ),
        },
    )
    direct_vm.mock_llm(
        r"(?s).*CREDIT WORKOUT DISCLOSURE REVIEW.*",
        review_response or ('{"outcome":"%s","confidence":"%s","rationale":"The update identifies the stated recovery assumption."}' % (outcome, confidence)),
    )
    contract.assess_workout("loan-1", proposal_id)


def pass_vote(contract, direct_vm, direct_bob, direct_alice, proposal_id="workout-1"):
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", proposal_id, True)
    direct_vm.sender = bytes.fromhex(LENDER_B[2:])
    contract.cast_vote("loan-1", proposal_id, True)
    proposal = contract.get_proposal("loan-1", proposal_id)
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(proposal["vote_ends_at"] + 1)))
    direct_vm.sender = direct_alice
    contract.finalize_workout("loan-1", proposal_id)


def test_lender_weighted_approval_applies_revised_terms_only_after_vote_window(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)

    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["status"] == "voting"
    assert proposal["yes_weight"] == 0

    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", "workout-1", True)
    direct_vm.sender = bytes.fromhex(LENDER_B[2:])
    contract.cast_vote("loan-1", "workout-1", True)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Voting window is still open"):
        contract.finalize_workout("loan-1", "workout-1")

    proposal = contract.get_proposal("loan-1", "workout-1")
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(proposal["vote_ends_at"] + 1)))
    contract.finalize_workout("loan-1", "workout-1")

    facility = contract.get_facility("loan-1")
    assert facility["status"] == "restructured"
    assert facility["outstanding_principal"] == 90000
    assert facility["revision"] == 3
    assert contract.get_proposal("loan-1", "workout-1")["status"] == "approved"
    with direct_vm.expect_revert("Workout proposal is not awaiting finalization"):
        contract.finalize_workout("loan-1", "workout-1")


def test_vote_window_starts_after_slow_assessment(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    direct_vm.sender = direct_bob
    contract.propose_workout(
        "loan-1",
        "slow-review",
        90000,
        int(time.time()) + 86400,
        "Extend 30 days; borrower forecasts recovery from contracted receivables.",
        "https://evidence.example/borrower-update",
    )
    original_deadline = contract.get_proposal("loan-1", "slow-review")["vote_ends_at"]
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(original_deadline + 1)))
    direct_vm.mock_web(
        r"(?s).*evidence\.example/borrower-update.*",
        {"status": 200, "body": "Acme Borrower Ltd update: contracted receivables are scheduled to settle."},
    )
    direct_vm.mock_llm(
        r"(?s).*CREDIT WORKOUT DISCLOSURE REVIEW.*",
        '{"outcome":"supported","confidence":"high","basis":"supporting_evidence","rationale":"The update supports the workout."}',
    )

    contract.assess_workout("loan-1", "slow-review")

    proposal = contract.get_proposal("loan-1", "slow-review")
    assert proposal["status"] == "voting"
    assert proposal["vote_ends_at"] > original_deadline + 1
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", "slow-review", True)
    assert contract.get_proposal("loan-1", "slow-review")["yes_weight"] == 6000


def test_borrower_cannot_register_lender_or_vote(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only the facility manager may do this"):
        contract.register_lender("loan-1", "0xdddddddddddddddddddddddddddddddddddddddd", 1)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    with direct_vm.expect_revert("Caller is not a registered lender"):
        contract.cast_vote("loan-1", "workout-1", True)


def test_lender_weight_cannot_exceed_committed_pool(direct_vm, direct_deploy, direct_alice):
    contract = deploy(direct_deploy)
    direct_vm.sender = direct_alice
    contract.create_facility("cap", BORROWER, "Acme Borrower Ltd", 100_000, int(time.time()) + 3600, 60, 600, 5000, 6000, 10000)
    contract.register_lender("cap", LENDER_A, 7000)
    with direct_vm.expect_revert("Registered lender weights exceed total pool weight"):
        contract.register_lender("cap", LENDER_B, 4000)


def test_vote_can_be_changed_once_per_lender_without_double_counting(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", "workout-1", True)
    contract.cast_vote("loan-1", "workout-1", False)
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["yes_weight"] == 0
    assert proposal["no_weight"] == 6000


def test_missing_quorum_rejects_workout_without_changing_facility_terms(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", "workout-1", True)
    proposal = contract.get_proposal("loan-1", "workout-1")
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(proposal["vote_ends_at"] + 1)))
    direct_vm.sender = direct_alice
    contract.finalize_workout("loan-1", "workout-1")
    assert contract.get_proposal("loan-1", "workout-1")["status"] == "no_quorum"
    facility = contract.get_facility("loan-1")
    assert facility["status"] == "workout_required"
    assert facility["outstanding_principal"] == 100000


def test_active_proposal_is_stale_if_manager_records_recovery_before_finalization(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", "workout-1", True)
    direct_vm.sender = bytes.fromhex(LENDER_B[2:])
    contract.cast_vote("loan-1", "workout-1", True)
    direct_vm.sender = direct_alice
    contract.record_recovery("loan-1", 20000)
    assert contract.get_proposal("loan-1", "workout-1")["status"] == "stale"
    facility = contract.get_facility("loan-1")
    assert facility["outstanding_principal"] == 80000
    assert facility["status"] == "workout_required"
    direct_vm.sender = bytes.fromhex(LENDER_B[2:])
    with direct_vm.expect_revert("Workout proposal is not open for voting"):
        contract.cast_vote("loan-1", "workout-1", True)


def test_cannot_open_workout_before_deterministic_cure_period_ends(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Facility is not past due beyond its cure period"):
        contract.mark_past_due("loan-1")


def test_proposal_cannot_increase_principal_or_have_expired_schedule(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Workout principal cannot exceed current outstanding principal"):
        contract.propose_workout("loan-1", "too-large", 100001, int(time.time()) + 86400, "Plan", "https://evidence.example/update")
    with direct_vm.expect_revert("Revised due date must be in the future"):
        contract.propose_workout("loan-1", "expired", 90000, int(time.time()) - 1, "Plan", "https://evidence.example/update")


def test_unclear_or_low_confidence_review_cannot_open_lender_ballot(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob, outcome="unclear", confidence="medium")
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["status"] == "review_blocked"
    assert proposal["review_outcome"] == "unclear"
    assert contract.get_facility("loan-1")["status"] == "workout_required"
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    with direct_vm.expect_revert("Workout proposal is not open for voting"):
        contract.cast_vote("loan-1", "workout-1", True)


def test_validator_rejects_a_materially_different_independent_review(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    assert direct_vm.run_validator() is True

    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r"(?s).*evidence\.example/borrower-update.*",
        {"status": 200, "body": "Acme Borrower Ltd revised update with materially different recovery evidence."},
    )
    direct_vm.mock_llm(
        r"(?s).*CREDIT WORKOUT DISCLOSURE REVIEW.*",
        '{"outcome":"supported","confidence":"high","basis":"supporting_evidence","rationale":"The changed source appears to support the proposal."}',
    )
    assert direct_vm.run_validator() is False


def test_unavailable_borrower_source_fails_closed(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob, source_status=503)
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["review_outcome"] == "source_failure"
    assert proposal["status"] == "review_blocked"
    assert contract.get_facility("loan-1")["status"] == "workout_required"


def test_source_must_explicitly_identify_registered_borrower_before_model_review(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(
        contract,
        direct_vm,
        direct_bob,
        source_body="Borrower update: contracted receivables are scheduled to settle within 30 days.",
        review_response='{"outcome":"supported","confidence":"high","basis":"supporting_evidence","rationale":"A matching recovery plan is described."}',
    )
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["status"] == "review_blocked"
    assert proposal["review_outcome"] == "unclear"
    assert proposal["review_confidence"] == "low"
    assert proposal["review_rationale"] == (
        "The retrieved source does not explicitly identify the facility borrower by its registered legal name."
    )


def test_http_access_denied_page_is_not_misclassified_as_borrower_evidence(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob, source_status=403, source_body="Access Denied")
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["review_outcome"] == "source_failure"
    assert proposal["status"] == "review_blocked"


def test_malformed_assessment_fails_closed_as_unclear(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob, review_response="not-json")
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["review_outcome"] == "unclear"
    assert proposal["review_confidence"] == "low"
    assert proposal["status"] == "review_blocked"


def test_unsupported_high_confidence_assessment_still_blocks_ballot(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob, outcome="unsupported", confidence="high")
    proposal = contract.get_proposal("loan-1", "workout-1")
    assert proposal["review_outcome"] == "unsupported"
    assert proposal["status"] == "review_blocked"


def test_majority_no_vote_rejects_proposal_after_quorum(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    direct_vm.sender = bytes.fromhex(LENDER_A[2:])
    contract.cast_vote("loan-1", "workout-1", False)
    direct_vm.sender = bytes.fromhex(LENDER_B[2:])
    contract.cast_vote("loan-1", "workout-1", False)
    proposal = contract.get_proposal("loan-1", "workout-1")
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(proposal["vote_ends_at"] + 1)))
    direct_vm.sender = direct_alice
    contract.finalize_workout("loan-1", "workout-1")
    assert contract.get_proposal("loan-1", "workout-1")["status"] == "rejected"
    facility = contract.get_facility("loan-1")
    assert facility["status"] == "workout_required"
    assert facility["outstanding_principal"] == 100000


def test_restructured_facility_can_reenter_cure_and_workout_lifecycle(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    new_facility(contract, direct_vm, direct_alice, direct_bob)
    mark_overdue(contract, direct_vm, direct_bob)
    propose(contract, direct_vm, direct_bob)
    pass_vote(contract, direct_vm, direct_bob, direct_alice)
    facility = contract.get_facility("loan-1")
    direct_vm.warp(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(facility["due_at"] + facility["grace_seconds"] + 1)))
    direct_vm.sender = direct_bob
    contract.mark_past_due("loan-1")
    assert contract.get_facility("loan-1")["status"] == "workout_required"
