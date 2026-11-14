"""No external publication occurs: publisher returns a payload dict only."""

import pytest
from boundary_factories import (
    TENANT_A,
    FakeManifestLookup,
    make_evidence_manifest,
    make_passing_b_gate_decision,
)
from saena_domain.measurement.evidence import EvidenceBundleManifest
from saena_experiment_attribution.boundary.errors import PublishRefusedError
from saena_experiment_attribution.boundary.outcome_publisher import OutcomePublisher

from .test_outcome_publisher import _base_kwargs


def test_incomplete_but_validly_sealed_bundle_is_not_publishable():
    manifest = make_evidence_manifest()
    incomplete = EvidenceBundleManifest.seal(
        tenant_id=manifest.tenant_id,
        run_id=manifest.run_id,
        experiment_id=manifest.experiment_id,
        entries=manifest.entries[:1],
    )
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, incomplete)
    with pytest.raises(PublishRefusedError):
        OutcomePublisher(manifest_lookup=lookup).publish(
            **_base_kwargs(
                decision=make_passing_b_gate_decision(),
                manifest_hash=incomplete.manifest_hash,
            )
        )


def test_insufficient_measurements_cannot_support_a_pass():
    manifest = make_evidence_manifest()
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash=manifest.manifest_hash
    )
    kwargs["did_result"] = kwargs["did_result"].model_copy(
        update={
            "signals": tuple(
                s.model_copy(update={"insufficient": True}) for s in kwargs["did_result"].signals
            )
        }
    )
    with pytest.raises(PublishRefusedError):
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)


@pytest.mark.parametrize("mutation", ["empty", "zero_lift", "missing_counts", "unrelated_layer"])
def test_pass_requires_supporting_measurement_payload(mutation):
    manifest = make_evidence_manifest()
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash=manifest.manifest_hash
    )
    signals = kwargs["did_result"].signals
    if mutation == "empty":
        signals = ()
    else:
        update = {
            "zero_lift": {"net_of_control_lift": 0.0},
            "missing_counts": {"sample_counts": {}},
            "unrelated_layer": {"layer": "referral"},
        }[mutation]
        signals = tuple(signal.model_copy(update=update) for signal in signals)
    kwargs["did_result"] = kwargs["did_result"].model_copy(update={"signals": signals})
    with pytest.raises(PublishRefusedError):
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "another-tenant"),
        ("experiment_id", "another-experiment"),
        ("manifest_hash", "sha256:" + "0" * 64),
    ],
)
def test_corrupt_lookup_cannot_cross_bind_evidence(field, value):
    manifest = make_evidence_manifest()

    class WrongLookup:
        def lookup(self, *args):
            return manifest

    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash=manifest.manifest_hash
    )
    kwargs[field] = value
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=WrongLookup()).publish(**kwargs)
    assert "evidence_manifest_identity_mismatch" in error.value.context["reasons"]


def test_mixed_policy_provenance_is_not_publishable():
    manifest = make_evidence_manifest()
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash=manifest.manifest_hash
    )
    kwargs["did_result"] = kwargs["did_result"].model_copy(
        update={"policy_provenance": "production"}
    )
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)
    assert "mixed_policy_provenance" in error.value.context["reasons"]


def test_same_basis_cannot_be_counted_as_two_independent_layers():
    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash="sha256:" + "0" * 64
    )
    did = kwargs["did_result"].model_copy(
        update={
            "signals": tuple(
                s.model_copy(update={"evidence_basis_id": "same-underlying-evidence"})
                for s in kwargs["did_result"].signals
            )
        }
    )
    manifest = make_evidence_manifest(decision=kwargs["decision"], did_result=did)
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    kwargs.update(did_result=did, manifest_hash=manifest.manifest_hash)
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)
    assert "insufficient_independent_measurements" in error.value.context["reasons"]


def test_complete_manifest_for_different_measurements_is_refused():
    manifest = make_evidence_manifest()
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash=manifest.manifest_hash
    )
    kwargs["did_result"] = kwargs["did_result"].model_copy(
        update={
            "signals": tuple(
                s.model_copy(update={"net_of_control_lift": 99.0})
                for s in kwargs["did_result"].signals
            )
        }
    )
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)
    assert "evidence_did_outputs_hash_mismatch" in error.value.context["reasons"]


def test_complete_manifest_for_different_decision_is_refused():
    manifest = make_evidence_manifest()
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    decision = make_passing_b_gate_decision()
    decision = decision.model_copy(
        update={"qualifying_layers": tuple(reversed(decision.qualifying_layers))}
    )
    kwargs = _base_kwargs(decision=decision, manifest_hash=manifest.manifest_hash)
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)
    assert "evidence_b_gate_decision_hash_mismatch" in error.value.context["reasons"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence", 0.123),
        ("raw_view", ()),
        ("control_adjusted_view", ()),
    ],
)
def test_report_fields_are_bound_to_decision_evidence(field, value):
    manifest = make_evidence_manifest()
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    decision = make_passing_b_gate_decision().model_copy(update={field: value})
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=lookup).publish(
            **_base_kwargs(
                decision=decision,
                manifest_hash=manifest.manifest_hash,
            )
        )
    assert "evidence_b_gate_decision_hash_mismatch" in error.value.context["reasons"]


def test_unclaimed_third_layer_cannot_supply_independence_for_claimed_layers():
    kwargs = _base_kwargs(
        decision=make_passing_b_gate_decision(), manifest_hash="sha256:" + "0" * 64
    )
    shared = tuple(
        signal.model_copy(update={"evidence_basis_id": "shared"})
        for signal in kwargs["did_result"].signals
    )
    extra = shared[0].model_copy(update={"layer": "referral", "evidence_basis_id": "independent"})
    did = kwargs["did_result"].model_copy(update={"signals": (*shared, extra)})
    manifest = make_evidence_manifest(decision=kwargs["decision"], did_result=did)
    lookup = FakeManifestLookup()
    lookup.put(TENANT_A, manifest)
    kwargs.update(did_result=did, manifest_hash=manifest.manifest_hash)
    with pytest.raises(PublishRefusedError) as error:
        OutcomePublisher(manifest_lookup=lookup).publish(**kwargs)
    assert "insufficient_independent_measurements" in error.value.context["reasons"]
