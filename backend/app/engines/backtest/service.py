"""
VesselOptima — Phase 13: Backtesting & Decision Replay Service

Integrates database persistence, run lifecycle management, determinism verification,
immutability enforcement, and demo scenario generation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engines.backtest.events import HistoricalEvent, HistoricalEventStream
from app.engines.backtest.orchestrator import BacktestExecutionResult, BacktestOrchestrator
from app.engines.backtest.reason_codes import (
    BacktestMode,
    BacktestRunStatus,
    DecisionFrequency,
    FailureReason,
    HistoricalEventType,
)
from app.models.domain import (
    BacktestAttribution,
    BacktestBenchmark,
    BacktestBenchmarkResult,
    BacktestConfiguration,
    BacktestDecision,
    BacktestLeakage,
    BacktestMetric,
    BacktestOutcome,
    BacktestRun,
    BacktestSnapshot,
    BacktestTimeline,
    RuntimeModeEnum,
)

logger = logging.getLogger("backtest.service")


class BacktestingService:
    """
    Service layer providing database persistence and orchestration for Phase 13 backtests.
    """
    def __init__(self, db: Session):
        self.db = db

    # ── Configuration Management ─────────────────────────────────────

    def create_configuration(
        self,
        name: str,
        start_timestamp: datetime,
        end_timestamp: datetime,
        description: Optional[str] = None,
        decision_frequency: DecisionFrequency = DecisionFrequency.EVENT_DRIVEN,
        decision_policy: str = "RECOMMENDED",
        dataset_versions: Optional[Dict[str, int]] = None,
        phase7_configuration: Optional[Dict[str, Any]] = None,
        phase8_enabled: bool = False,
        phase9_enabled: bool = False,
        phase10_configuration: Optional[Dict[str, Any]] = None,
        benchmark_set: Optional[List[str]] = None,
        seed: int = 42,
        created_by: str = "institutional_risk_manager",
    ) -> BacktestConfiguration:
        """
        Creates an immutable BacktestConfiguration record.
        """
        versions = dataset_versions or {"maritime_data": 1}
        benchmarks = benchmark_set or [
            "NO_ACTION",
            "CONTINUE_CURRENT_EMPLOYMENT",
            "FIRST_FEASIBLE",
            "BEST_EXPECTED_CONTRIBUTION",
            "HISTORICAL_ACTUAL",
        ]
        config_code = f"CFG-BT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}-{seed}"

        # Hash configuration
        raw = {
            "name": name,
            "start": start_timestamp.isoformat(),
            "end": end_timestamp.isoformat(),
            "frequency": decision_frequency.value,
            "policy": decision_policy,
            "dataset_versions": versions,
            "benchmarks": sorted(benchmarks),
            "seed": seed,
        }
        cfg_hash = hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()

        config = BacktestConfiguration(
            config_code=config_code,
            name=name,
            description=description,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            decision_frequency=decision_frequency.value,
            decision_policy=decision_policy,
            dataset_versions=versions,
            phase7_configuration=phase7_configuration or {},
            phase8_enabled=phase8_enabled,
            phase9_enabled=phase9_enabled,
            phase10_configuration=phase10_configuration or {},
            benchmark_set=benchmarks,
            seed=seed,
            configuration_hash=cfg_hash,
            created_by=created_by,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_configuration(self, config_id: int) -> Optional[BacktestConfiguration]:
        return self.db.query(BacktestConfiguration).filter(BacktestConfiguration.id == config_id).first()

    def list_configurations(self, limit: int = 50) -> List[BacktestConfiguration]:
        return self.db.query(BacktestConfiguration).order_by(BacktestConfiguration.id.desc()).limit(limit).all()

    # ── Backtest Run Execution & Persistence ─────────────────────────

    def execute_and_persist_run(
        self,
        name: str,
        start_timestamp: datetime,
        end_timestamp: datetime,
        mode: BacktestMode = BacktestMode.OUTCOME_BACKTEST,
        frequency: DecisionFrequency = DecisionFrequency.EVENT_DRIVEN,
        dataset_versions: Optional[Dict[str, int]] = None,
        event_stream: Optional[HistoricalEventStream] = None,
        historical_actuals: Optional[List[Dict[str, Any]]] = None,
        phase8_enabled: bool = False,
        phase9_enabled: bool = False,
        seed: int = 42,
        benchmark_set: Optional[List[str]] = None,
        strict_leakage: bool = True,
        created_by: str = "fleet_analyst",
    ) -> BacktestRun:
        """
        Coordinates full backtest simulation, persists results immutably, and returns DB model.
        """
        run_code = f"RUN-BT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Ensure configuration exists
        config = self.create_configuration(
            name=f"Config for {name}",
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            decision_frequency=frequency,
            dataset_versions=dataset_versions,
            phase8_enabled=phase8_enabled,
            phase9_enabled=phase9_enabled,
            benchmark_set=benchmark_set,
            seed=seed,
            created_by=created_by,
        )

        # 2. Build or obtain HistoricalEventStream
        stream = event_stream or self.generate_demo_event_stream(start_timestamp, end_timestamp)

        # 3. Create initial RUNNING record
        db_run = BacktestRun(
            name=name,
            run_code=run_code,
            configuration_id=config.id,
            mode=mode.value,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            decision_frequency=frequency.value,
            dataset_versions=config.dataset_versions,
            status=BacktestRunStatus.RUNNING.value,
            runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
            seed=seed,
            software_version="1.0.0",
            solver_version="HiGHS-1.5.1",
            configuration_hash=config.configuration_hash,
            created_by=created_by,
        )
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)

        # 4. Execute Replay Orchestrator
        orchestrator = BacktestOrchestrator(
            mode=mode,
            frequency=frequency,
            dataset_versions=config.dataset_versions,
            phase8_enabled=phase8_enabled,
            phase9_enabled=phase9_enabled,
            seed=seed,
            benchmark_set=config.benchmark_set,
            strict_leakage=strict_leakage,
        )

        result: BacktestExecutionResult = orchestrator.execute_backtest(
            run_code=run_code,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            event_stream=stream,
            historical_actuals=historical_actuals,
        )

        # 5. Persist child records
        # A. Snapshots & Decisions
        decision_id_map: Dict[str, int] = {}
        for dec in result.decisions:
            snap = BacktestSnapshot(
                snapshot_code=f"SNAP-{dec.decision_code}",
                run_id=db_run.id,
                snapshot_timestamp=dec.decision_timestamp,
                dataset_versions=result.dataset_versions,
                vessel_count=len(dec.assignments),
                cargo_count=sum(1 for a in dec.assignments if a.get("cargo_id") is not None),
                market_state_hash=dec.decision_hash,
                snapshot_hash=dec.decision_hash,
                snapshot_payload={"assignments": dec.assignments},
            )
            self.db.add(snap)
            self.db.flush()

            db_dec = BacktestDecision(
                decision_code=dec.decision_code,
                run_id=db_run.id,
                snapshot_id=snap.id,
                decision_timestamp=dec.decision_timestamp,
                phase7_run_id=dec.phase7_run_id,
                phase8_run_id=dec.phase8_run_id,
                phase9_run_id=dec.phase9_run_id,
                phase10_run_id=dec.phase10_run_id,
                recommendation=dec.recommendation,
                assignments=dec.assignments,
                expected_contribution=dec.expected_contribution_usd,
                risk_metrics=dec.risk_metrics,
                governance_state=dec.governance_state,
                decision_hash=dec.decision_hash,
            )
            self.db.add(db_dec)
            self.db.flush()
            decision_id_map[dec.decision_code] = db_dec.id

        # B. Outcomes
        for out in result.outcomes:
            # Extract decision code if in outcome_code
            dec_id = None
            for dcode, did in decision_id_map.items():
                if dcode in out.outcome_code:
                    dec_id = did
                    break

            db_out = BacktestOutcome(
                outcome_code=out.outcome_code,
                run_id=db_run.id,
                decision_id=dec_id,
                vessel_id=out.vessel_id,
                cargo_id=out.cargo_id,
                realized_revenue=out.realized_revenue_usd,
                realized_bunker_cost=out.realized_bunker_cost_usd,
                realized_port_cost=out.realized_port_cost_usd,
                realized_voyage_cost=out.realized_voyage_cost_usd,
                realized_ballast_cost=out.realized_ballast_cost_usd,
                realized_idle_cost=out.realized_idle_cost_usd,
                realized_contribution=out.realized_contribution_usd,
                expected_contribution=out.expected_contribution_usd,
                economic_error=out.economic_error_usd,
                planned_departure=out.planned_departure,
                actual_departure=out.actual_departure,
                planned_arrival=out.planned_arrival,
                actual_arrival=out.actual_arrival,
                schedule_delay_days=out.schedule_delay_days,
                idle_days=out.idle_days,
                ballast_days=out.ballast_days,
                cargo_completed=out.cargo_completed,
                outcome_hash=out.outcome_hash,
            )
            self.db.add(db_out)

        # C. Benchmarks
        benchmark_id_map: Dict[str, int] = {}
        for bm_code in config.benchmark_set:
            existing = self.db.query(BacktestBenchmark).filter(BacktestBenchmark.benchmark_code == bm_code).first()
            if not existing:
                existing = BacktestBenchmark(
                    benchmark_code=bm_code,
                    name=bm_code.replace("_", " ").title(),
                    strategy_type=bm_code,
                    description=f"Institutional baseline: {bm_code}",
                )
                self.db.add(existing)
                self.db.flush()
            benchmark_id_map[bm_code] = existing.id

        for bres in result.benchmark_results:
            bm_id = benchmark_id_map.get(bres.get("strategy_type", "NO_ACTION"))
            dec_id = decision_id_map.get(bres.get("decision_code", ""))
            ts_str = bres.get("step_timestamp", start_timestamp.isoformat())
            ts = datetime.fromisoformat(ts_str) if isinstance(ts_str, str) else ts_str

            db_bres = BacktestBenchmarkResult(
                run_id=db_run.id,
                benchmark_id=bm_id,
                decision_id=dec_id,
                step_timestamp=ts,
                assignments=bres.get("assignments", []),
                realized_contribution=float(bres.get("realized_contribution_usd", 0.0)),
                vessel_utilization=float(bres.get("vessel_utilization_pct", 0.0)),
                details={"benchmark_name": bres.get("benchmark_name")},
            )
            self.db.add(db_bres)

        # D. Metrics
        if result.metrics_summary:
            ms = result.metrics_summary
            for cat, sub in [
                ("ECONOMIC", ms.to_dict()["economic"]),
                ("RELATIVE", ms.to_dict()["relative"]),
                ("DECISION", ms.to_dict()["decision"]),
                ("RISK", ms.to_dict()["risk"]),
                ("OPERATIONAL", ms.to_dict()["operational"]),
            ]:
                for k, v in sub.items():
                    if isinstance(v, (int, float)):
                        self.db.add(
                            BacktestMetric(
                                run_id=db_run.id,
                                metric_category=cat,
                                metric_name=k,
                                metric_value=float(v),
                                details={},
                            )
                        )

        # E. Attributions
        for cat, att_list in result.attributions.items():
            for att in att_list:
                self.db.add(
                    BacktestAttribution(
                        run_id=db_run.id,
                        attribution_type=att.attribution_type,
                        entity_id=att.entity_id,
                        entity_name=att.entity_name,
                        incremental_contribution=att.incremental_contribution_usd,
                        decision_count=att.decision_count,
                        utilization_pct=att.utilization_pct,
                        details=att.details,
                    )
                )

        # F. Leakage
        if result.leakage_report:
            for v in result.leakage_report.violations:
                self.db.add(
                    BacktestLeakage(
                        run_id=db_run.id,
                        leakage_type=v.leakage_type.value if hasattr(v.leakage_type, "value") else str(v.leakage_type),
                        severity=v.severity,
                        field_name=v.field_name,
                        decision_timestamp=v.decision_timestamp,
                        information_timestamp=v.information_timestamp,
                        details=v.details,
                    )
                )

        # 6. Finalize Run Status & Metrics Summary
        db_run.status = result.status.value
        db_run.backtest_hash = result.backtest_hash
        db_run.metrics_summary = result.metrics_summary.to_dict() if result.metrics_summary else {}
        db_run.warnings_count = len(result.leakage_report.violations) if result.leakage_report else 0
        db_run.failure_reason = result.failure_reason.value if result.failure_reason else None
        db_run.execution_time_seconds = result.execution_time_seconds

        self.db.commit()
        self.db.refresh(db_run)
        return db_run

    def get_run(self, run_id: int) -> Optional[BacktestRun]:
        return self.db.query(BacktestRun).filter(BacktestRun.id == run_id).first()

    def list_runs(self, limit: int = 50) -> List[BacktestRun]:
        return self.db.query(BacktestRun).order_by(BacktestRun.id.desc()).limit(limit).all()

    # ── Demo Event Stream Generator ──────────────────────────────────

    def generate_demo_event_stream(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> HistoricalEventStream:
        """
        Creates a rich, deterministic historical event stream representing
        active vessels, coal/iron ore cargoes, freight rates, bunker prices, and realization events.
        """
        stream = HistoricalEventStream()
        base_t = start_time

        # 1. Vessels
        vessels_spec = [
            (1, "VO Amber Leader", "Handysize", 35000.0, "INPRT", 650.0),
            (2, "VO Diamond Wave", "Supramax", 58000.0, "INBOM", 820.0),
            (3, "VO Emerald Trader", "Ultramax", 64000.0, "SGSIN", 900.0),
            (4, "VO Sapphire Star", "Panamax", 75000.0, "AEJEA", 1100.0),
        ]
        for vid, vname, vclass, dwt, port, fuel in vessels_spec:
            ev = HistoricalEvent(
                event_id=f"EV-VESSEL-{vid}",
                event_type=HistoricalEventType.VESSEL_AVAILABILITY,
                event_timestamp=base_t,
                availability_timestamp=base_t,
                source_dataset_id="demo-historical-maritime",
                source_dataset_version=1,
                entity_id=str(vid),
                payload={
                    "name": vname,
                    "vessel_class": vclass,
                    "dwt": dwt,
                    "open_port": port,
                    "is_available": True,
                    "fuel_ifo_remaining": fuel,
                },
            )
            stream.add_event(ev)

        # 2. Cargoes
        cargoes_spec = [
            (101, "Paradip Coal 32k MT", "INPRT", "INBOM", 32000.0, 24.5, 0),
            (102, "Vizag Bauxite 55k MT", "INVTZ", "INMAA", 55000.0, 18.0, 3),
            (103, "Singapore Iron Ore 60k MT", "SGSIN", "INBOM", 60000.0, 28.0, 7),
            (104, "Fujairah Gypsum 70k MT", "AEFJR", "INBOM", 70000.0, 19.5, 12),
        ]
        for cid, cname, origin, dest, qty, rate, day_offset in cargoes_spec:
            c_ts = base_t + timedelta(days=day_offset)
            ev = HistoricalEvent(
                event_id=f"EV-CARGO-{cid}",
                event_type=HistoricalEventType.CARGO_AVAILABLE,
                event_timestamp=c_ts,
                availability_timestamp=c_ts,
                source_dataset_id="demo-historical-maritime",
                source_dataset_version=1,
                entity_id=str(cid),
                payload={
                    "name": cname,
                    "origin_port": origin,
                    "destination_port": dest,
                    "quantity_mt": qty,
                    "freight_rate_usd": rate,
                    "is_active": True,
                },
            )
            stream.add_event(ev)

        # 3. Freight and Bunker Price Updates
        routes = [
            ("INPRT_INBOM", 24.5),
            ("INVTZ_INMAA", 18.0),
            ("SGSIN_INBOM", 28.0),
            ("AEFJR_INBOM", 19.5),
        ]
        for rk, rate in routes:
            ev = HistoricalEvent(
                event_id=f"EV-FR-{rk}",
                event_type=HistoricalEventType.FREIGHT_UPDATE,
                event_timestamp=base_t,
                availability_timestamp=base_t,
                source_dataset_id="demo-historical-market",
                source_dataset_version=1,
                entity_id=rk,
                payload={"route_key": rk, "rate_usd_mt": rate},
            )
            stream.add_event(ev)

        ports = [("INPRT", 580.0), ("INBOM", 610.0), ("SGSIN", 540.0), ("AEFJR", 560.0)]
        for pcode, price in ports:
            ev = HistoricalEvent(
                event_id=f"EV-BNK-{pcode}",
                event_type=HistoricalEventType.BUNKER_PRICE,
                event_timestamp=base_t,
                availability_timestamp=base_t,
                source_dataset_id="demo-historical-market",
                source_dataset_version=1,
                entity_id=pcode,
                payload={"port_code": pcode, "price_usd_mt": price},
            )
            stream.add_event(ev)

        # 4. Operational Realization Events (minor port delay on Day 15)
        delay_ev = HistoricalEvent(
            event_id="EV-OP-DELAY-01",
            event_type=HistoricalEventType.OPERATIONAL_EVENT,
            event_timestamp=base_t + timedelta(days=15),
            availability_timestamp=base_t + timedelta(days=15),
            source_dataset_id="demo-historical-ops",
            source_dataset_version=1,
            entity_id="2",  # Vessel 2
            payload={"description": "Monsoon berth congestion at INBOM", "delay_days": 1.5},
        )
        stream.add_event(delay_ev)

        return stream
