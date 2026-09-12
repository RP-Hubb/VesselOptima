"""
VesselOptima — Phase 1-13 Hardening Regression Test
Finding 1: Runtime Mode Engine Enforcement & Persistence Verification

Proves:
1. In OFFLINE_DEMO, decision-producing engines persist runtime_mode=OFFLINE_DEMO and report OFFLINE_DEMO provenance.
2. In LIVE mode, engines fail closed with LiveSourceUnavailableError (HTTP 503 equivalent) rather than silently executing offline demo data.
3. Decision-producing engines dynamically read runtime mode from the database / active session, persisting runtime_mode=LIVE when in LIVE mode.
4. LiveSourceUnavailableError and OfflineNetworkProhibitedError are fully operational.
"""

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import LiveSourceUnavailableError, OfflineNetworkProhibitedError
from app.models.domain import (
    RuntimeModeEnum,
    RuntimeModeEvent,
    OptimizationRun,
    DecisionRun,
    RiskRun,
    FeasibilityCheck,
    EmploymentOpportunity,
    ProcurementEvaluation,
    DecisionPackage,
    GovernanceDataset,
)
from app.services.runtime import (
    get_active_runtime_mode,
    check_live_source_available,
    register_live_source,
    unregister_live_source,
)
from app.engines.decision.service import DecisionService
from app.engines.optimization.service import OptimizationService
from app.engines.feasibility.service import FeasibilityService
from app.engines.employment.service import EmploymentService
from app.engines.procurement.service import ProcurementService
from app.engines.backtest.service import BacktestingService
from app.engines.risk.risk_service import RiskService
from app.engines.governance.service import GovernanceService
from app.engines.data.service import DataGovernanceService


def test_offline_demo_persistence_and_provenance(db: Session):
    """Verifies that in OFFLINE_DEMO mode, engines persist OFFLINE_DEMO."""
    # Ensure active mode is OFFLINE_DEMO
    event = RuntimeModeEvent(
        mode=RuntimeModeEnum.OFFLINE_DEMO,
        mode_session_id=str(uuid4()),
        actor="tester",
        reason="Testing OFFLINE_DEMO persistence",
        selected_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    active_mode = get_active_runtime_mode(db)
    assert active_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 1. Feasibility engine
    feas_service = FeasibilityService(db=db)
    feas_res = feas_service.evaluate_assignment(cargo_id=1, vessel_id=1, persist=True)
    assert feas_res["provenance"]["runtime_mode"] == "OFFLINE_DEMO"
    saved_fc = db.query(FeasibilityCheck).order_by(FeasibilityCheck.id.desc()).first()
    assert saved_fc is not None
    assert saved_fc.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 2. Employment engine
    emp_service = EmploymentService(db=db)
    emp_res = emp_service.evaluate_employment_candidate(vessel_id=1, cargo_id=1, persist=True)
    assert emp_res["provenance"]["data_mode"] == "OFFLINE_DEMO"
    saved_emp = db.query(EmploymentOpportunity).order_by(EmploymentOpportunity.id.desc()).first()
    assert saved_emp is not None
    assert saved_emp.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 3. Procurement engine
    proc_service = ProcurementService(db=db)
    proc_res = proc_service.evaluate_cargo_strategies(cargo_id=1, persist=True)
    saved_pe = db.query(ProcurementEvaluation).order_by(ProcurementEvaluation.id.desc()).first()
    assert saved_pe is not None
    assert saved_pe.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 4. Optimization engine
    opt_service = OptimizationService(db=db)
    opt_res = opt_service.solve_fleet_assignment(scenario="DEMO_FLEET", persist=True)
    saved_opt = db.query(OptimizationRun).filter(OptimizationRun.run_id == opt_res.run_id).first()
    assert saved_opt is not None
    assert saved_opt.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 5. Risk engine
    risk_service = RiskService(db=db)
    risk_res = risk_service.simulate_plan_risk(optimization_run_id=opt_res.run_id, persist=True)
    saved_risk = db.query(RiskRun).filter(RiskRun.run_id == risk_res.run_id).first()
    assert saved_risk is not None
    assert saved_risk.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 6. Decision engine
    dec_service = DecisionService(db=db)
    dec_res = dec_service.evaluate_decision(optimization_run_id=opt_res.run_id)
    saved_dec = db.query(DecisionRun).filter(DecisionRun.run_id == dec_res.run_id).first()
    assert saved_dec is not None
    assert saved_dec.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO

    # 7. Governance package
    gov_service = GovernanceService(db=db)
    pkg_res = gov_service.create_package_from_decision(decision_run_id=dec_res.run_id)
    saved_pkg = db.query(DecisionPackage).filter(DecisionPackage.package_id == pkg_res["package_id"]).first()
    assert saved_pkg is not None
    assert saved_pkg.runtime_mode == RuntimeModeEnum.OFFLINE_DEMO


def test_live_mode_fails_closed_without_live_sources(db: Session):
    """Verifies that in LIVE mode, engines fail closed with LiveSourceUnavailableError."""
    # Switch to LIVE
    event = RuntimeModeEvent(
        mode=RuntimeModeEnum.LIVE,
        mode_session_id=str(uuid4()),
        actor="tester",
        reason="Testing LIVE mode fail-closed behavior",
        selected_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    active_mode = get_active_runtime_mode(db)
    assert active_mode == RuntimeModeEnum.LIVE

    try:
        # 1. Direct check helper
        with pytest.raises(LiveSourceUnavailableError) as exc_info:
            check_live_source_available("test_live_feed", db=db)
        assert "test_live_feed" in str(exc_info.value)
        assert "unavailable" in str(exc_info.value).lower()

        # 2. OptimizationService in LIVE mode
        opt_service = OptimizationService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            opt_service.solve_fleet_assignment(scenario="DEMO_FLEET", persist=False)

        # 3. DecisionService in LIVE mode
        dec_service = DecisionService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            dec_service.evaluate_decision(optimization_run_id="OPT-LIVE-TEST")

        # 4. FeasibilityService in LIVE mode
        feas_service = FeasibilityService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            feas_service.evaluate_assignment(cargo_id=1, vessel_id=1, persist=False)

        # 5. EmploymentService in LIVE mode
        emp_service = EmploymentService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            emp_service.evaluate_employment_candidate(vessel_id=1, cargo_id=1, persist=False)

        # 6. ProcurementService in LIVE mode
        proc_service = ProcurementService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            proc_service.evaluate_cargo_strategies(cargo_id=1, persist=False)

        # 7. BacktestService in LIVE mode
        backtest_service = BacktestingService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            backtest_service.execute_and_persist_run(
                name="Test Live Backtest",
                start_timestamp=datetime(2026, 8, 1, tzinfo=timezone.utc),
                end_timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc),
            )

        # 8. RiskService in LIVE mode
        risk_service = RiskService(db=db)
        with pytest.raises(LiveSourceUnavailableError):
            risk_service.simulate_plan_risk(optimization_run_id="OPT-LIVE-TEST", persist=False)
    finally:
        db.add(RuntimeModeEvent(
            mode=RuntimeModeEnum.OFFLINE_DEMO,
            mode_session_id=str(uuid4()),
            actor="tester",
            reason="Restoring OFFLINE_DEMO",
            selected_at=datetime.now(timezone.utc),
        ))
        db.commit()


def test_live_mode_persists_live_when_active(db: Session):
    """
    Verifies that when LIVE mode is active (and live adapter availability is satisfied),
    engines persist runtime_mode=LIVE, proving mode is genuinely dynamic and NOT hardcoded.
    """
    event = RuntimeModeEvent(
        mode=RuntimeModeEnum.LIVE,
        mode_session_id=str(uuid4()),
        actor="tester",
        reason="Testing LIVE mode dynamic persistence",
        selected_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    assert get_active_runtime_mode(db) == RuntimeModeEnum.LIVE

    # Register all live sources as active/operational for this test
    register_live_source("*")
    try:
        # 1. Feasibility persistence in LIVE
        feas_service = FeasibilityService(db=db)
        feas_res = feas_service.evaluate_assignment(cargo_id=1, vessel_id=1, persist=True)
        assert feas_res["provenance"]["runtime_mode"] == "LIVE"
        assert feas_res["provenance"]["is_authoritative_real_world_data"] is True
        saved_fc = db.query(FeasibilityCheck).order_by(FeasibilityCheck.id.desc()).first()
        assert saved_fc.runtime_mode == RuntimeModeEnum.LIVE

        # 2. Employment persistence in LIVE (using vessel 2, cargo 2 for unique candidate_id)
        emp_service = EmploymentService(db=db)
        emp_res = emp_service.evaluate_employment_candidate(vessel_id=2, cargo_id=2, persist=True)
        assert emp_res["provenance"]["data_mode"] == "LIVE"
        saved_emp = db.query(EmploymentOpportunity).filter(EmploymentOpportunity.candidate_id == emp_res["candidate_id"]).first()
        assert saved_emp is not None
        assert saved_emp.runtime_mode == RuntimeModeEnum.LIVE

        # 3. Optimization persistence in LIVE
        opt_service = OptimizationService(db=db)
        opt_res = opt_service.solve_fleet_assignment(scenario="DEMO_FLEET", persist=True)
        saved_opt = db.query(OptimizationRun).filter(OptimizationRun.run_id == opt_res.run_id).first()
        assert saved_opt.runtime_mode == RuntimeModeEnum.LIVE

        # 4. Data Governance dataset ingestion in LIVE
        data_service = DataGovernanceService(db=db)
        sample_csv = (
            "vessel_id,vessel_name,dwt,loa,beam,draft,service_speed,fuel_consumption\n"
            "V99,Test Vessel,75000,225.0,32.2,14.0,13.5,28.0"
        )
        ds_res = data_service.import_dataset(
            dataset_type="VESSEL_MASTER",
            name="Live Ingested Particulars",
            source_payload=sample_csv,
            filename="live_particulars.csv",
        )
        saved_ds = db.query(GovernanceDataset).filter(GovernanceDataset.dataset_id == ds_res["dataset_id"]).first()
        assert saved_ds.runtime_mode == RuntimeModeEnum.LIVE
    finally:
        unregister_live_source("*")
        db.add(RuntimeModeEvent(
            mode=RuntimeModeEnum.OFFLINE_DEMO,
            mode_session_id=str(uuid4()),
            actor="tester",
            reason="Restoring OFFLINE_DEMO",
            selected_at=datetime.now(timezone.utc),
        ))
        db.commit()


def test_offline_network_prohibited_error():
    """Verifies OfflineNetworkProhibitedError exception semantics."""
    err = OfflineNetworkProhibitedError()
    assert err.status_code == 403
    assert "External network access is prohibited in OFFLINE_DEMO mode" in err.message
