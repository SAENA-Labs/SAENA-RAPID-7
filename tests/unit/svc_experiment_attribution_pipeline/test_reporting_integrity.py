"""Customer-report trust regressions using explicitly synthetic data only."""

from dataclasses import replace

import pytest
from pipeline_factories import make_happy_path_inputs, make_policies, make_ports
from saena_domain.measurement.b_gate import GatePolicy, PolicyProvenance
from saena_domain.measurement.reason_codes import ReasonCode
from saena_experiment_attribution.pipeline import OutcomeStatus, run_measurement


@pytest.mark.parametrize("field", ["baseline_evidence", "treatment_evidence", "control_evidence"])
@pytest.mark.parametrize("missing_all", [True, False])
def test_missing_provenance_for_any_signal_blocks_success(field, missing_all):
    inputs, registration = make_happy_path_inputs()
    original = getattr(inputs, field)
    inputs = replace(inputs, **{field: () if missing_all else original[:1]})
    outcome = run_measurement(inputs, make_ports(), make_policies(registration))
    assert outcome.status is OutcomeStatus.UNDETERMINED
    assert ReasonCode.MISSING_RAW_EVIDENCE_REF in outcome.reason_codes


def test_production_gate_cannot_launder_fixture_policy_provenance():
    inputs, registration = make_happy_path_inputs()
    policies = make_policies(registration)
    policies = replace(
        policies,
        gate_policy=GatePolicy(
            version="1.0.0",
            hash="sha256:" + "d" * 64,
            provenance=PolicyProvenance.PRODUCTION,
        ),
    )
    outcome = run_measurement(inputs, make_ports(), policies)
    # Mechanism status is separate from provenance; neither is live evidence.
    assert not outcome.is_production


def test_evidence_manifest_binds_actual_values_even_when_means_unchanged():
    inputs, registration = make_happy_path_inputs()
    policies = make_policies(registration)
    first = run_measurement(inputs, make_ports(), policies)
    signal = inputs.signals[0]
    changed = signal.model_copy(
        update={
            "post_treatment": signal.post_treatment.model_copy(
                update={"repeat_values": (19.0, 20.0, 21.0)},
            )
        }
    )
    changed_inputs = replace(inputs, signals=(changed, *inputs.signals[1:]))
    second = run_measurement(changed_inputs, make_ports(), policies)
    assert first.status is second.status is OutcomeStatus.PASS
    assert first.evidence_bundle_ref != second.evidence_bundle_ref


@pytest.mark.parametrize("gate_prod", [False, True])
@pytest.mark.parametrize("grs_prod", [False, True])
@pytest.mark.parametrize("did_prod", [False, True])
def test_production_provenance_requires_all_policies(monkeypatch, gate_prod, grs_prod, did_prod):
    # Synthetic injected policy decisions test flag propagation ONLY. No real
    # production signature, authorization, observation or effect is asserted.
    from saena_domain.measurement import grs

    inputs, registration = make_happy_path_inputs()
    policies = make_policies(registration)
    synthetic_grs = grs.evaluate_grs_eligibility(inputs.grs_inputs, bundle=policies.grs_bundle)
    synthetic_grs = replace(
        synthetic_grs,
        is_production_valid=grs_prod,
        provenance=grs.PolicyProvenance.PRODUCTION
        if grs_prod
        else grs.PolicyProvenance.TEST_FIXTURE,
    )
    monkeypatch.setattr(grs, "evaluate_grs_eligibility", lambda *a, **kw: synthetic_grs)
    policies = replace(
        policies,
        gate_policy=GatePolicy(
            version="1.0.0",
            hash="sha256:" + "d" * 64,
            provenance=PolicyProvenance.PRODUCTION if gate_prod else PolicyProvenance.TEST_FIXTURE,
        ),
        did_policy=policies.did_policy.model_copy(
            update={
                "provenance": "production" if did_prod else "test_fixture",
            }
        ),
    )
    outcome = run_measurement(inputs, make_ports(), policies)
    assert outcome.is_production is (gate_prod and grs_prod and did_prod)


@pytest.mark.parametrize("field", ["timestamps", "observation_ids"])
def test_evidence_hash_binds_observation_identity_and_time(field):
    from datetime import timedelta

    inputs, registration = make_happy_path_inputs()
    policies = make_policies(registration)
    before = run_measurement(inputs, make_ports(), policies)
    signal = inputs.signals[0]
    cell = signal.post_treatment
    value = (
        tuple(at + timedelta(minutes=1) for at in cell.timestamps)
        if field == "timestamps"
        else tuple("changed-" + oid for oid in cell.observation_ids)
    )
    changed = signal.model_copy(update={"post_treatment": cell.model_copy(update={field: value})})
    after = run_measurement(
        replace(inputs, signals=(changed, *inputs.signals[1:])), make_ports(), policies
    )
    assert before.evidence_bundle_ref != after.evidence_bundle_ref
