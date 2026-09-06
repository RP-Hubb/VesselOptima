"""
VesselOptima — Phase 13: Backtesting & Decision Replay REST API Router
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.backtest.reason_codes import BacktestMode, DecisionFrequency
from app.engines.backtest.service import BacktestingService
from app.models.domain import (
    BacktestAttribution,
    BacktestBenchmarkResult,
    BacktestConfiguration,
    BacktestDecision,
    BacktestLeakage,
    BacktestMetric,
    BacktestOutcome,
    BacktestRun,
    BacktestTimeline,
)
from app.schemas.backtest import (
    BacktestAttributionItem,
    BacktestBenchmarkResultItem,
    BacktestCompareRequest,
    BacktestCompareResponse,
    BacktestCompareRunItem,
    BacktestConfigurationCreate,
    BacktestConfigurationResponse,
    BacktestDecisionItem,
    BacktestLeakageItem,
    BacktestMetricItem,
    BacktestOutcomeItem,
    BacktestRunCreate,
    BacktestRunDetail,
    BacktestRunSummary,
    BacktestTimelineStepItem,
)

logger = logging.getLogger("api.backtest")

router = APIRouter(prefix="/backtest", tags=["Historical Backtesting"])


# ── Configurations ───────────────────────────────────────────────────

@router.post("/configurations", response_model=BacktestConfigurationResponse)
def create_configuration(
    req: BacktestConfigurationCreate,
    db: Session = Depends(get_db),
) -> Any:
    """Creates a new immutable BacktestConfiguration."""
    try:
        svc = BacktestingService(db)
        freq = DecisionFrequency(req.decision_frequency)
        cfg = svc.create_configuration(
            name=req.name,
            start_timestamp=req.start_timestamp,
            end_timestamp=req.end_timestamp,
            description=req.description,
            decision_frequency=freq,
            decision_policy=req.decision_policy,
            dataset_versions=req.dataset_versions,
            phase7_configuration=req.phase7_configuration,
            phase8_enabled=req.phase8_enabled,
            phase9_enabled=req.phase9_enabled,
            phase10_configuration=req.phase10_configuration,
            benchmark_set=req.benchmark_set,
            seed=req.seed,
            created_by=req.created_by,
        )
        return cfg
    except Exception as e:
        logger.error(f"Error creating backtest configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create configuration: {str(e)}")


@router.get("/configurations", response_model=List[BacktestConfigurationResponse])
def list_configurations(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Any:
    """Lists historical backtest configurations."""
    svc = BacktestingService(db)
    return svc.list_configurations(limit=limit)


@router.get("/configurations/{config_id}", response_model=BacktestConfigurationResponse)
def get_configuration(
    config_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves a specific backtest configuration by ID."""
    svc = BacktestingService(db)
    cfg = svc.get_configuration(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return cfg


# ── Backtest Runs ────────────────────────────────────────────────────

@router.post("/runs", response_model=BacktestRunDetail)
def create_and_execute_run(
    req: BacktestRunCreate,
    db: Session = Depends(get_db),
) -> Any:
    """
    Creates and executes a deterministic historical backtest run.
    Reconstructs point-in-time state, applies Phase 7 HiGHS MILP,
    computes realized outcomes, and compares against benchmark policies.
    """
    try:
        svc = BacktestingService(db)
        mode = BacktestMode(req.mode)
        freq = DecisionFrequency(req.frequency)

        run = svc.execute_and_persist_run(
            name=req.name,
            start_timestamp=req.start_timestamp,
            end_timestamp=req.end_timestamp,
            mode=mode,
            frequency=freq,
            dataset_versions=req.dataset_versions,
            phase8_enabled=req.phase8_enabled,
            phase9_enabled=req.phase9_enabled,
            seed=req.seed,
            benchmark_set=req.benchmark_set,
            strict_leakage=req.strict_leakage,
            created_by=req.created_by,
        )
        return run
    except Exception as e:
        logger.error(f"Error executing backtest run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {str(e)}")


@router.get("/runs", response_model=List[BacktestRunSummary])
def list_runs(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Any:
    """Lists backtest runs chronologically."""
    svc = BacktestingService(db)
    return svc.list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=BacktestRunDetail)
def get_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves detailed results for a specific backtest run."""
    svc = BacktestingService(db)
    run = svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run


# ── Granular Replay Views ────────────────────────────────────────────

@router.get("/runs/{run_id}/timeline", response_model=List[BacktestTimelineStepItem])
def get_run_timeline(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns the chronological decision timeline for a backtest run."""
    steps = db.query(BacktestTimeline).filter(BacktestTimeline.run_id == run_id).order_by(BacktestTimeline.step_index.asc()).all()
    return steps


@router.get("/runs/{run_id}/decisions", response_model=List[BacktestDecisionItem])
def get_run_decisions(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns the frozen historical decisions produced across all decision milestones."""
    decisions = db.query(BacktestDecision).filter(BacktestDecision.run_id == run_id).order_by(BacktestDecision.decision_timestamp.asc()).all()
    return decisions


@router.get("/runs/{run_id}/outcomes", response_model=List[BacktestOutcomeItem])
def get_run_outcomes(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns realized operational and economic outcomes calculated from subsequent realization events."""
    outcomes = db.query(BacktestOutcome).filter(BacktestOutcome.run_id == run_id).order_by(BacktestOutcome.id.asc()).all()
    return outcomes


@router.get("/runs/{run_id}/benchmarks", response_model=List[BacktestBenchmarkResultItem])
def get_run_benchmarks(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns the allocations and realized returns of baseline benchmark strategies."""
    results = db.query(BacktestBenchmarkResult).filter(BacktestBenchmarkResult.run_id == run_id).all()
    return results


@router.get("/runs/{run_id}/metrics", response_model=List[BacktestMetricItem])
def get_run_metrics(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns portfolio and fleet-level aggregate performance metrics."""
    metrics = db.query(BacktestMetric).filter(BacktestMetric.run_id == run_id).all()
    return metrics


@router.get("/runs/{run_id}/attribution", response_model=List[BacktestAttributionItem])
def get_run_attribution(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns contribution attributions disaggregated across vessels, cargoes, and drivers."""
    attribs = db.query(BacktestAttribution).filter(BacktestAttribution.run_id == run_id).all()
    return attribs


@router.get("/runs/{run_id}/leakage", response_model=List[BacktestLeakageItem])
def get_run_leakage(
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Returns the information leakage audit ledger for this run."""
    leakages = db.query(BacktestLeakage).filter(BacktestLeakage.run_id == run_id).all()
    return leakages


# ── Run Comparison ───────────────────────────────────────────────────

@router.post("/compare", response_model=BacktestCompareResponse)
def compare_runs(
    req: BacktestCompareRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Compares two or more backtest runs side by side on realized contribution,
    incremental gain, relative improvement %, and schedule reliability.
    """
    runs = db.query(BacktestRun).filter(BacktestRun.id.in_(req.run_ids)).all()
    if len(runs) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid runs are required for comparison.")

    run_items: List[BacktestCompareRunItem] = []
    for r in runs:
        summary = r.metrics_summary or {}
        econ = summary.get("economic", {})
        rel = summary.get("relative", {})
        ops = summary.get("operational", {})

        tot_contrib = float(econ.get("total_realized_contribution_usd", 0.0))
        inc_contrib = float(rel.get("incremental_contribution_usd", 0.0))
        rel_imp = float(rel.get("relative_improvement_pct", 0.0))
        util = float(ops.get("vessel_utilization_pct", 0.0))
        delay = float(ops.get("total_schedule_delay_days", 0.0))

        run_items.append(
            BacktestCompareRunItem(
                run_id=r.id,
                run_code=r.run_code or f"RUN-{r.id}",
                name=r.name,
                mode=r.mode,
                status=r.status,
                total_realized_contribution=tot_contrib,
                incremental_contribution=inc_contrib,
                relative_improvement_pct=rel_imp,
                vessel_utilization_pct=util,
                schedule_delay_days=delay,
                warnings_count=r.warnings_count,
                backtest_hash=r.backtest_hash or "N/A",
            )
        )

    # Determine winner
    sorted_by_contrib = sorted(run_items, key=lambda x: x.total_realized_contribution, reverse=True)
    winner = sorted_by_contrib[0]
    runner_up = sorted_by_contrib[1]
    delta = winner.total_realized_contribution - runner_up.total_realized_contribution

    notes = [
        f"Run '{winner.name}' delivered superior economic contribution (${winner.total_realized_contribution:,.2f}).",
        f"Incremental margin over second place: +${delta:,.2f}.",
    ]

    return BacktestCompareResponse(
        runs=run_items,
        winner_run_id=winner.run_id,
        delta_contribution_usd=round(delta, 2),
        comparison_notes=notes,
    )


# ── Institutional Demo Presets ───────────────────────────────────────

@router.post("/demo/{scenario}", response_model=BacktestRunDetail)
def run_demo_scenario(
    scenario: str = "q1_2025_market_rally",
    db: Session = Depends(get_db),
) -> Any:
    """
    Executes a pre-packaged institutional historical simulation scenario.
    Provides immediate one-click demonstration of decision replay and benchmark outperformance.
    """
    svc = BacktestingService(db)
    start_t = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    end_t = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)

    scenario_names = {
        "q1_2025_market_rally": "Q1 2025 Indian Ocean Market Rally",
        "monsoon_disruption": "SW Monsoon Port Congestion & Disruption",
        "bunker_price_spike": "Red Sea Routing & Bunker Price Volatility",
    }
    name = scenario_names.get(scenario, f"Historical Simulation: {scenario.replace('_', ' ').title()}")

    run = svc.execute_and_persist_run(
        name=name,
        start_timestamp=start_t,
        end_timestamp=end_t,
        mode=BacktestMode.OUTCOME_BACKTEST,
        frequency=DecisionFrequency.EVENT_DRIVEN,
        seed=100,
        created_by="institutional_demo_user",
    )
    return run
