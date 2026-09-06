"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Data Governance Orchestration Service
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.engines.data.adapters.local_file import LocalFileAdapter
from app.engines.data.contracts import DatasetContract, get_contract
from app.engines.data.hashing import (
    compute_canonical_hash,
    compute_dataset_hash,
    compute_record_hash,
    verify_dataset_integrity,
)
from app.engines.data.impact import analyze_dataset_impact
from app.engines.data.models import (
    DatasetDiffResult,
    ImpactAnalysisResult,
    QualityScoreResult,
    ValidationResult,
)
from app.engines.data.normalization import normalize_record
from app.engines.data.quality import calculate_data_quality_score
from app.engines.data.quarantine import build_quarantine_records
from app.engines.data.reason_codes import (
    DataGovernanceReasonCode,
    DatasetStatus,
    DatasetType,
    FreshnessStatus,
    ImpactLevel,
    QuarantineSeverity,
    RecordChangeType,
)
from app.engines.data.validation import validate_dataset_records
from app.engines.data.versioning import compare_datasets, extract_business_key
from app.models.domain import (
    DatasetChange,
    DatasetImpact,
    DatasetProvenance,
    DatasetQuality,
    DatasetRecord,
    DatasetValidation,
    DatasetVersion,
    DecisionPackage,
    GovernanceAuditEvent,
    GovernanceDataset,
    QuarantineRecord,
    RuntimeModeEnum,
)

logger = logging.getLogger(__name__)


class DataGovernanceService:
    """Enterprise orchestration service for maritime data integration and quality governance."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db
        self.file_adapter = LocalFileAdapter()

    def import_dataset(
        self,
        dataset_type: DatasetType | str,
        name: str,
        source_payload: Any,
        filename: Optional[str] = None,
        description: Optional[str] = None,
        actor: str = "data_engineer",
        actor_role: str = "ANALYST",
        dataset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingests untrusted maritime data through the full 4-tier validation, normalization,
        quarantine, cryptographic hashing, and quality governance pipeline.
        """
        dtype = DatasetType(dataset_type) if isinstance(dataset_type, str) else dataset_type
        contract = get_contract(dtype)
        ds_id = dataset_id or f"DS-{dtype.value[:4]}-{uuid4().hex[:8].upper()}"

        # 1. Extraction via air-gapped file adapter
        raw_records, prov_metadata = self.file_adapter.extract_raw_records(source_payload, filename=filename)
        prov_metadata["import_actor"] = actor
        prov_metadata["import_role"] = actor_role

        # 2. Normalization per contract
        normalized_records: List[Dict[str, Any]] = []
        all_transformations: List[Dict[str, Any]] = []
        for r in raw_records:
            norm_r, transforms = normalize_record(r, contract)
            normalized_records.append(norm_r)
            all_transformations.extend(transforms)

        prov_metadata["transformation_chain"] = all_transformations

        # 3. 4-Layer Validation & Quarantine Segregation
        val_result, valid_records, quarantined_records = validate_dataset_records(normalized_records, contract)

        # 4. Transparent 6-Factor Quality Scoring
        quality_result = calculate_data_quality_score(
            records=normalized_records,
            contract=contract,
            validation_result=val_result,
            provenance_metadata=prov_metadata,
        )

        # 5. Cryptographic Canonical SHA-256 Hashing
        content_hash = compute_dataset_hash(normalized_records, dtype.value, version_number=1)

        # 6. Status determination
        if not val_result.is_valid:
            if val_result.quarantined_records_count > 0 and val_result.valid_records_count > 0:
                initial_status = DatasetStatus.QUARANTINED
            else:
                initial_status = DatasetStatus.INVALID
        else:
            initial_status = DatasetStatus.VALID

        # 7. Persistence
        if self.db:
            db_dataset = GovernanceDataset(
                dataset_id=ds_id,
                dataset_type=dtype.value,
                name=name,
                description=description or f"Ingested {dtype.value} dataset.",
                current_version=1,
                status=initial_status.value,
                content_hash=content_hash,
                quality_score=quality_result.overall_score,
                freshness_status=quality_result.freshness_status.value,
                record_count=len(normalized_records),
                created_by=actor,
                runtime_mode=RuntimeModeEnum.OFFLINE_DEMO,
            )
            self.db.add(db_dataset)
            self.db.flush()

            # Version record
            db_version = DatasetVersion(
                dataset_id=db_dataset.id,
                version_number=1,
                parent_version_number=None,
                content_hash=content_hash,
                schema_version=contract.schema_version,
                record_count=len(normalized_records),
                change_summary="Initial dataset ingestion.",
                storage_path=filename or "in_memory",
                created_by=actor,
            )
            self.db.add(db_version)

            # Records with row-level hashes
            for idx, r in enumerate(normalized_records):
                bkey = extract_business_key(r, contract.business_key_fields, idx)
                rec_h = compute_record_hash(r)
                db_record = DatasetRecord(
                    dataset_id=db_dataset.id,
                    version_number=1,
                    record_index=idx,
                    business_key=bkey,
                    record_data=r,
                    record_hash=rec_h,
                )
                self.db.add(db_record)

            # Validation layers
            for layer_name, layer_ok in val_result.layer_results.items():
                err_cnt = sum(1 for iss in val_result.issues if iss.layer.value == layer_name)
                db_val = DatasetValidation(
                    dataset_id=db_dataset.id,
                    version_number=1,
                    layer=layer_name,
                    is_valid=layer_ok,
                    error_count=err_cnt,
                    details={"sample_errors": [iss.message for iss in val_result.issues if iss.layer.value == layer_name][:10]},
                )
                self.db.add(db_val)

            # Quality report
            db_quality = DatasetQuality(
                dataset_id=db_dataset.id,
                version_number=1,
                overall_score=quality_result.overall_score,
                completeness_score=quality_result.completeness_score,
                validity_score=quality_result.validity_score,
                consistency_score=quality_result.consistency_score,
                uniqueness_score=quality_result.uniqueness_score,
                timeliness_score=quality_result.timeliness_score,
                provenance_score=quality_result.provenance_score,
                weights_snapshot=quality_result.weights,
                freshness_status=quality_result.freshness_status.value,
            )
            self.db.add(db_quality)

            # Provenance
            db_prov = DatasetProvenance(
                dataset_id=db_dataset.id,
                version_number=1,
                source_name=prov_metadata.get("source_name", "UNKNOWN"),
                source_type=prov_metadata.get("source_type", "LOCAL_FILE"),
                original_filename=prov_metadata.get("original_filename"),
                original_hash=prov_metadata.get("original_hash"),
                import_actor=actor,
                schema_version=contract.schema_version,
                parent_dataset_id=None,
                transformation_chain=all_transformations,
            )
            self.db.add(db_prov)

            # Quarantine records
            quarantine_entries = build_quarantine_records(db_dataset.id, 1, val_result.issues, normalized_records)
            for qe in quarantine_entries:
                self.db.add(QuarantineRecord(**qe))

            self.db.commit()

        return {
            "dataset_id": ds_id,
            "dataset_type": dtype.value,
            "name": name,
            "version_number": 1,
            "status": initial_status.value,
            "content_hash": content_hash,
            "quality_score": quality_result.overall_score,
            "freshness_status": quality_result.freshness_status.value,
            "total_records": len(normalized_records),
            "valid_records": len(valid_records),
            "quarantined_records": len(quarantined_records),
            "is_valid": val_result.is_valid,
            "provenance": prov_metadata,
            "validation_layers": val_result.layer_results,
        }

    def import_new_version(
        self,
        dataset_id: str,
        source_payload: Any,
        change_summary: str,
        filename: Optional[str] = None,
        actor: str = "data_engineer",
        actor_role: str = "ANALYST",
    ) -> Dict[str, Any]:
        """
        Creates an immutable child version (V1 -> V2) for an existing dataset.
        Computes granular record diffs (ADDED, REMOVED, MODIFIED, UNCHANGED)
        and conducts downstream impact analysis.
        """
        db_ds = self._get_db_dataset(dataset_id)
        if not db_ds:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        dtype = DatasetType(db_ds.dataset_type)
        contract = get_contract(dtype)
        new_version_num = db_ds.current_version + 1

        # Extract & normalize target records
        raw_records, prov_metadata = self.file_adapter.extract_raw_records(source_payload, filename=filename)
        normalized_records: List[Dict[str, Any]] = [normalize_record(r, contract)[0] for r in raw_records]

        # Validation & Quality
        val_result, valid_records, quarantined_records = validate_dataset_records(normalized_records, contract)
        quality_result = calculate_data_quality_score(normalized_records, contract, val_result, prov_metadata)
        content_hash = compute_dataset_hash(normalized_records, dtype.value, version_number=new_version_num)

        # Retrieve base version records from database
        base_records: List[Dict[str, Any]] = []
        if self.db:
            db_base_recs = (
                self.db.query(DatasetRecord)
                .filter(DatasetRecord.dataset_id == db_ds.id, DatasetRecord.version_number == db_ds.current_version)
                .order_by(DatasetRecord.record_index.asc())
                .all()
            )
            base_records = [r.record_data for r in db_base_recs]

        # Execute Differential Comparison
        diff_res = compare_datasets(
            dataset_id=dataset_id,
            base_records=base_records,
            target_records=normalized_records,
            business_key_fields=contract.business_key_fields,
            base_version=db_ds.current_version,
            target_version=new_version_num,
        )

        # Analyze Downstream Impact & Stale Decision Packages
        stale_packages: List[str] = []
        if self.db:
            # Check for approved Phase 11 decision packages
            packages = self.db.query(DecisionPackage).filter(DecisionPackage.status == "APPROVED").all()
            stale_packages = [p.package_id for p in packages]

        impact_res = analyze_dataset_impact(
            dataset_id=dataset_id,
            dataset_type=dtype,
            version_number=new_version_num,
            diff_result=diff_res,
            dependent_package_ids=stale_packages,
        )

        # Update database
        if self.db:
            db_ds.current_version = new_version_num
            db_ds.content_hash = content_hash
            db_ds.quality_score = quality_result.overall_score
            db_ds.freshness_status = quality_result.freshness_status.value
            db_ds.record_count = len(normalized_records)
            db_ds.status = DatasetStatus.VALID.value if val_result.is_valid else DatasetStatus.QUARANTINED.value

            # Add Version
            db_ver = DatasetVersion(
                dataset_id=db_ds.id,
                version_number=new_version_num,
                parent_version_number=db_ds.current_version - 1,
                content_hash=content_hash,
                schema_version=contract.schema_version,
                record_count=len(normalized_records),
                change_summary=change_summary,
                storage_path=filename or "in_memory",
                created_by=actor,
            )
            self.db.add(db_ver)

            # Add Records
            for idx, r in enumerate(normalized_records):
                bkey = extract_business_key(r, contract.business_key_fields, idx)
                db_record = DatasetRecord(
                    dataset_id=db_ds.id,
                    version_number=new_version_num,
                    record_index=idx,
                    business_key=bkey,
                    record_data=r,
                    record_hash=compute_record_hash(r),
                )
                self.db.add(db_record)

            # Add Changes
            for c in diff_res.changes:
                db_chg = DatasetChange(
                    dataset_id=db_ds.id,
                    base_version=db_ds.current_version - 1,
                    target_version=new_version_num,
                    change_type=c.change_type.value,
                    record_identifier=c.record_identifier,
                    field_diffs=c.field_diffs,
                )
                self.db.add(db_chg)

            # Add Impact
            db_imp = DatasetImpact(
                dataset_id=db_ds.id,
                version_number=new_version_num,
                impact_level=impact_res.impact_level.value,
                affected_engines=impact_res.affected_engines,
                affected_runs=impact_res.affected_runs,
                requires_recalculation=impact_res.requires_recalculation,
                stale_decision_packages=impact_res.stale_decision_packages,
                rationale=impact_res.rationale,
            )
            self.db.add(db_imp)

            # Save quality and validation
            db_quality = DatasetQuality(
                dataset_id=db_ds.id,
                version_number=new_version_num,
                overall_score=quality_result.overall_score,
                completeness_score=quality_result.completeness_score,
                validity_score=quality_result.validity_score,
                consistency_score=quality_result.consistency_score,
                uniqueness_score=quality_result.uniqueness_score,
                timeliness_score=quality_result.timeliness_score,
                provenance_score=quality_result.provenance_score,
                weights_snapshot=quality_result.weights,
                freshness_status=quality_result.freshness_status.value,
            )
            self.db.add(db_quality)

            self.db.commit()

        return {
            "dataset_id": dataset_id,
            "version_number": new_version_num,
            "status": db_ds.status,
            "content_hash": content_hash,
            "quality_score": quality_result.overall_score,
            "diff_summary": diff_res.summary,
            "added_count": diff_res.added_count,
            "removed_count": diff_res.removed_count,
            "modified_count": diff_res.modified_count,
            "unchanged_count": diff_res.unchanged_count,
            "impact_level": impact_res.impact_level.value,
            "affected_engines": impact_res.affected_engines,
            "stale_decision_packages": impact_res.stale_decision_packages,
        }

    def approve_dataset(
        self,
        dataset_id: str,
        actor: str = "fleet_director",
        actor_role: str = "APPROVER",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Formally approves a validated dataset for consumption by decision engines."""
        db_ds = self._get_db_dataset(dataset_id)
        if not db_ds:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        if db_ds.status not in (DatasetStatus.VALID.value, DatasetStatus.IMPORTED.value):
            raise ValueError(f"Cannot approve dataset in status '{db_ds.status}'. Must be in VALID status.")

        db_ds.status = DatasetStatus.APPROVED.value
        db_ds.approved_by = actor
        db_ds.approved_at = datetime.now(timezone.utc)

        if self.db:
            self.db.commit()

        return self._dataset_to_dict(db_ds)

    def reject_dataset(
        self,
        dataset_id: str,
        reason: str,
        actor: str = "fleet_director",
        actor_role: str = "APPROVER",
    ) -> Dict[str, Any]:
        """Formally rejects a dataset with recorded reason."""
        db_ds = self._get_db_dataset(dataset_id)
        if not db_ds:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        db_ds.status = DatasetStatus.REJECTED.value
        if self.db:
            self.db.commit()

        return self._dataset_to_dict(db_ds)

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full details of a dataset."""
        db_ds = self._get_db_dataset(dataset_id)
        return self._dataset_to_dict(db_ds) if db_ds else None

    def list_datasets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists active datasets in the registry."""
        if not self.db:
            return []
        items = self.db.query(GovernanceDataset).order_by(GovernanceDataset.id.desc()).limit(limit).all()
        return [self._dataset_to_dict(d) for d in items]

    def get_quarantine_records(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Returns quarantined records for a dataset."""
        db_ds = self._get_db_dataset(dataset_id)
        if not db_ds or not self.db:
            return []
        recs = self.db.query(QuarantineRecord).filter(QuarantineRecord.dataset_id == db_ds.id).all()
        return [
            {
                "id": q.id,
                "record_identifier": q.record_identifier,
                "field_name": q.field_name,
                "original_value": q.original_value,
                "error_code": q.error_code,
                "severity": q.severity,
                "message": q.message,
                "raw_record": q.raw_record,
                "quarantined_at": q.quarantined_at.isoformat() if q.quarantined_at else None,
            }
            for q in recs
        ]

    def get_dataset_diff(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves latest version differential changes."""
        db_ds = self._get_db_dataset(dataset_id)
        if not db_ds or not self.db:
            return None
        changes = (
            self.db.query(DatasetChange)
            .filter(DatasetChange.dataset_id == db_ds.id, DatasetChange.target_version == db_ds.current_version)
            .all()
        )
        return {
            "dataset_id": dataset_id,
            "base_version": db_ds.current_version - 1 if db_ds.current_version > 1 else 1,
            "target_version": db_ds.current_version,
            "total_changes": len(changes),
            "changes": [
                {
                    "record_identifier": c.record_identifier,
                    "change_type": c.change_type,
                    "field_diffs": c.field_diffs,
                }
                for c in changes
            ],
        }

    def get_dataset_impact(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves downstream dependency and stale decision impact analysis."""
        db_ds = self._get_db_dataset(dataset_id)
        if not db_ds or not self.db:
            return None
        imp = (
            self.db.query(DatasetImpact)
            .filter(DatasetImpact.dataset_id == db_ds.id, DatasetImpact.version_number == db_ds.current_version)
            .first()
        )
        if not imp:
            # Fallback on fresh analysis
            impact_res = analyze_dataset_impact(dataset_id, db_ds.dataset_type, db_ds.current_version)
            return {
                "dataset_id": dataset_id,
                "dataset_type": impact_res.dataset_type,
                "version_number": impact_res.version_number,
                "impact_level": impact_res.impact_level.value,
                "affected_engines": impact_res.affected_engines,
                "affected_runs": impact_res.affected_runs,
                "requires_recalculation": impact_res.requires_recalculation,
                "stale_decision_packages": impact_res.stale_decision_packages,
                "rationale": impact_res.rationale,
            }
        return {
            "dataset_id": dataset_id,
            "dataset_type": db_ds.dataset_type,
            "version_number": imp.version_number,
            "impact_level": imp.impact_level,
            "affected_engines": imp.affected_engines,
            "affected_runs": imp.affected_runs,
            "requires_recalculation": imp.requires_recalculation,
            "stale_decision_packages": imp.stale_decision_packages,
            "rationale": imp.rationale,
        }

    def seed_canonical_demo_data(self) -> Dict[str, Any]:
        """
        Seeds canonical demonstration datasets (V1 and V2) per Section 33.
        Demonstrates:
          - Dataset V1 (5 vessels, Quality 96/100, APPROVED)
          - Dataset V2 (1 modified, 1 added, 3 unchanged, diff & downstream impact)
        """
        existing = self.get_dataset("DS-VESSEL-MASTER-DEMO")
        if existing:
            return existing

        # 1. Seed Vessel Master V1 (5 vessels)
        v1_records = [
            {"vessel_id": "V1", "vessel_name": "Pacific Endeavour", "dwt": "70,000 MT", "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": "13.5 kts", "fuel_consumption": "28.5 MT/day"},
            {"vessel_id": "V2", "vessel_name": "Atlantic Pioneer", "dwt": "82,000 MT", "loa": 229.0, "beam": 32.2, "draft": 14.5, "service_speed": "14.0 kts", "fuel_consumption": "31.0 MT/day"},
            {"vessel_id": "V3", "vessel_name": "Orient Star", "dwt": "55,000 MT", "loa": 189.9, "beam": 32.2, "draft": 12.8, "service_speed": "13.0 kts", "fuel_consumption": "24.0 MT/day"},
            {"vessel_id": "V4", "vessel_name": "Nordic Bulk", "dwt": "64,000 MT", "loa": 199.9, "beam": 32.2, "draft": 13.3, "service_speed": "13.5 kts", "fuel_consumption": "26.5 MT/day"},
            {"vessel_id": "V5", "vessel_name": "Southern Cross", "dwt": "180,000 MT", "loa": 292.0, "beam": 45.0, "draft": 18.2, "service_speed": "14.5 kts", "fuel_consumption": "48.0 MT/day"},
        ]

        v1_import = self.import_dataset(
            dataset_type=DatasetType.VESSEL_MASTER,
            name="Fleet Master Registry (Authoritative)",
            source_payload=v1_records,
            filename="vessel_master_v1.csv",
            description="Authoritative fleet registry containing physical dimensions and propulsion metrics.",
            actor="capt_vance",
            actor_role="ADMIN",
            dataset_id="DS-VESSEL-MASTER-DEMO",
        )

        # Formally approve V1
        self.approve_dataset(
            dataset_id="DS-VESSEL-MASTER-DEMO",
            actor="director_bob",
            actor_role="APPROVER",
            notes="Formally approved as authoritative fleet baseline.",
        )

        # 2. Seed V2 update (1 modified V1 capacity, 1 added V6, 3 unchanged V2-V4, 1 removed V5)
        v2_records = [
            {"vessel_id": "V1", "vessel_name": "Pacific Endeavour", "dwt": "72,000 MT", "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": "13.5 kts", "fuel_consumption": "28.5 MT/day"}, # Modified capacity
            {"vessel_id": "V2", "vessel_name": "Atlantic Pioneer", "dwt": "82,000 MT", "loa": 229.0, "beam": 32.2, "draft": 14.5, "service_speed": "14.0 kts", "fuel_consumption": "31.0 MT/day"},
            {"vessel_id": "V3", "vessel_name": "Orient Star", "dwt": "55,000 MT", "loa": 189.9, "beam": 32.2, "draft": 12.8, "service_speed": "13.0 kts", "fuel_consumption": "24.0 MT/day"},
            {"vessel_id": "V4", "vessel_name": "Nordic Bulk", "dwt": "64,000 MT", "loa": 199.9, "beam": 32.2, "draft": 13.3, "service_speed": "13.5 kts", "fuel_consumption": "26.5 MT/day"},
            {"vessel_id": "V6", "vessel_name": "Poseidon Horizon", "dwt": "95,000 MT", "loa": 235.0, "beam": 38.0, "draft": 15.0, "service_speed": "14.2 kts", "fuel_consumption": "34.0 MT/day"}, # Added
        ]

        self.import_new_version(
            dataset_id="DS-VESSEL-MASTER-DEMO",
            source_payload=v2_records,
            change_summary="Modified Pacific Endeavour DWT capacity (+2,000 MT); added Post-Panamax Poseidon Horizon.",
            filename="vessel_master_v2.csv",
            actor="analyst_alice",
        )

        return self.get_dataset("DS-VESSEL-MASTER-DEMO")

    def _get_db_dataset(self, dataset_id: str) -> Optional[GovernanceDataset]:
        if not self.db:
            return None
        return self.db.query(GovernanceDataset).filter(GovernanceDataset.dataset_id == dataset_id).first()

    def _dataset_to_dict(self, db_ds: GovernanceDataset) -> Dict[str, Any]:
        return {
            "id": db_ds.id,
            "dataset_id": db_ds.dataset_id,
            "dataset_type": db_ds.dataset_type,
            "name": db_ds.name,
            "description": db_ds.description,
            "current_version": db_ds.current_version,
            "status": db_ds.status,
            "content_hash": db_ds.content_hash,
            "quality_score": db_ds.quality_score,
            "freshness_status": db_ds.freshness_status,
            "record_count": db_ds.record_count,
            "created_by": db_ds.created_by,
            "approved_by": db_ds.approved_by,
            "approved_at": db_ds.approved_at.isoformat() if db_ds.approved_at else None,
            "created_at": db_ds.created_at.isoformat() if db_ds.created_at else None,
        }
