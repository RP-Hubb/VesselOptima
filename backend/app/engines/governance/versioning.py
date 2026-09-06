"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Package Version Comparison & Reproducibility Engine
"""

from typing import Any, Dict, List, Optional

from app.engines.governance.models import (
    PackageComparisonResult,
    ReproductionResult,
)


def compare_decision_packages(
    base_pkg: Dict[str, Any],
    target_pkg: Dict[str, Any],
) -> PackageComparisonResult:
    """
    Compares two package versions (e.g. V1 vs V2) and isolates all evidence deltas
    and recommendation shifts.
    """
    base_id = base_pkg.get("package_id", "V1")
    base_ver = base_pkg.get("version_number", 1)
    target_id = target_pkg.get("package_id", "V2")
    target_ver = target_pkg.get("version_number", 2)

    base_rec = base_pkg.get("recommendation_type", "")
    target_rec = target_pkg.get("recommendation_type", "")
    rec_changed = base_rec != target_rec

    base_score = float(base_pkg.get("decision_score", 0.0))
    target_score = float(target_pkg.get("decision_score", 0.0))
    score_delta = round(target_score - base_score, 1)

    base_contrib = float(base_pkg.get("expected_contribution", 0.0))
    target_contrib = float(target_pkg.get("expected_contribution", 0.0))
    contrib_delta = round(target_contrib - base_contrib, 2)

    base_cvar = float(base_pkg.get("cvar_95", 0.0))
    target_cvar = float(target_pkg.get("cvar_95", 0.0))
    cvar_delta = round(target_cvar - base_cvar, 2)

    base_lp = float(base_pkg.get("loss_probability", 0.0))
    target_lp = float(target_pkg.get("loss_probability", 0.0))
    lp_delta = round(target_lp - base_lp, 4)

    base_rel = float(base_pkg.get("plan_reliability", 0.0))
    target_rel = float(target_pkg.get("plan_reliability", 0.0))
    rel_delta = round(target_rel - base_rel, 1)

    changed_factors: List[str] = []
    if abs(contrib_delta) > 1.0:
        changed_factors.append(
            f"Expected contribution: ${target_contrib:,.0f} ({contrib_delta:+,.0f})"
        )
    if abs(cvar_delta) > 1.0:
        changed_factors.append(
            f"95% CVaR tail loss: ${target_cvar:,.0f} ({cvar_delta:+,.0f})"
        )
    if abs(lp_delta) > 0.001:
        changed_factors.append(
            f"Loss probability: {target_lp*100:.1f}% ({lp_delta*100:+.1f}%)"
        )
    if abs(rel_delta) > 0.1:
        changed_factors.append(
            f"Plan reliability score: {target_rel:.1f} pts ({rel_delta:+.1f} pts)"
        )
    if rec_changed:
        changed_factors.append(f"Recommendation flip: {base_rec} -> {target_rec}")

    summary = (
        f"Decision Package V{base_ver} vs V{target_ver}: "
        + (f"Recommendation flipped from {base_rec} to {target_rec}. " if rec_changed else "Recommendation held stable. ")
        + f"Net contribution changed by ${contrib_delta:+,.0f}, CVaR tail risk changed by ${cvar_delta:+,.0f}, "
        + f"and composite Decision Score changed by {score_delta:+.1f} pts."
    )

    return PackageComparisonResult(
        base_package_id=base_id,
        base_version=base_ver,
        target_package_id=target_id,
        target_version=target_ver,
        decision_changed=rec_changed or abs(score_delta) >= 5.0,
        recommendation_flip=f"{base_rec} -> {target_rec}" if rec_changed else None,
        score_delta=score_delta,
        contribution_delta=contrib_delta,
        cvar_delta=cvar_delta,
        loss_prob_delta=lp_delta,
        reliability_delta=rel_delta,
        changed_factors=changed_factors,
        comparison_summary=summary,
    )


def verify_decision_reproducibility(
    stored_package: Dict[str, Any],
    recomputed_result: Dict[str, Any],
) -> ReproductionResult:
    """
    Evaluates whether an existing decision package can be reproducibly reconstructed
    from its upstream run references and configuration.
    """
    pkg_id = stored_package.get("package_id", "UNKNOWN")
    mismatches: List[str] = []

    orig_rec = stored_package.get("recommendation_type")
    repro_rec = recomputed_result.get("recommendation_type")
    if orig_rec != repro_rec:
        mismatches.append(f"Recommendation mismatch: expected '{orig_rec}', got '{repro_rec}'")

    orig_score = float(stored_package.get("decision_score", 0.0))
    repro_score = float(recomputed_result.get("decision_score", 0.0))
    if abs(orig_score - repro_score) > 0.5:
        mismatches.append(f"Score mismatch: expected {orig_score}, got {repro_score}")

    orig_out_hash = stored_package.get("output_hash")
    repro_out_hash = recomputed_result.get("output_hash")
    if orig_out_hash and repro_out_hash and orig_out_hash != repro_out_hash:
        mismatches.append("Cryptographic output hash mismatch between original and recomputed run.")

    is_reproducible = len(mismatches) == 0

    return ReproductionResult(
        package_id=pkg_id,
        status="REPRODUCIBLE" if is_reproducible else "REPRODUCTION_MISMATCH",
        is_reproducible=is_reproducible,
        original_score=orig_score,
        reproduced_score=repro_score,
        original_recommendation=str(orig_rec),
        reproduced_recommendation=str(repro_rec),
        mismatched_fields=mismatches,
        details={
            "stored_package_id": pkg_id,
            "optimization_run_id": stored_package.get("optimization_run_id"),
            "decision_run_id": stored_package.get("decision_run_id"),
            "configuration_version": stored_package.get("configuration_version"),
        },
    )
