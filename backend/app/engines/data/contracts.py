"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Dataset Contracts, Schemas & Declarative Validation Profiles
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.engines.data.reason_codes import DatasetType


@dataclass(frozen=True)
class FieldContract:
    """Contract definition for an individual dataset field."""
    name: str
    field_type: str  # "string", "float", "integer", "datetime", "boolean"
    required: bool = True
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[Tuple[str, ...]] = None
    description: str = ""


@dataclass(frozen=True)
class DatasetContract:
    """Contract governing schema, types, physical limits, and business keys for a dataset."""
    dataset_type: DatasetType
    schema_version: str
    business_key_fields: Tuple[str, ...]
    fields: Dict[str, FieldContract]
    default_currency: str = "USD"
    freshness_hours_current: float = 24.0
    freshness_hours_aging: float = 72.0


# ── Canonical Dataset Contract Registry ────────────────────────────────

VESSEL_MASTER_CONTRACT = DatasetContract(
    dataset_type=DatasetType.VESSEL_MASTER,
    schema_version="1.0.0",
    business_key_fields=("vessel_id",),
    fields={
        "vessel_id": FieldContract("vessel_id", "string", required=True, description="Unique vessel identifier"),
        "vessel_name": FieldContract("vessel_name", "string", required=True, description="Vessel registry name"),
        "imo_number": FieldContract("imo_number", "string", required=False, description="International Maritime Org number"),
        "dwt": FieldContract("dwt", "float", required=True, unit="MT", min_value=100.0, description="Deadweight tonnage"),
        "grt": FieldContract("grt", "float", required=False, unit="MT", min_value=100.0, description="Gross registered tonnage"),
        "loa": FieldContract("loa", "float", required=True, unit="meters", min_value=10.0, max_value=450.0, description="Length overall"),
        "beam": FieldContract("beam", "float", required=True, unit="meters", min_value=3.0, max_value=70.0, description="Extreme breadth"),
        "draft": FieldContract("draft", "float", required=True, unit="meters", min_value=1.0, max_value=30.0, description="Maximum operational draft"),
        "vessel_type": FieldContract("vessel_type", "string", required=False, description="Vessel structural classification"),
        "flag": FieldContract("flag", "string", required=False, description="Maritime flag state"),
        "year_built": FieldContract("year_built", "integer", required=False, min_value=1950, max_value=2030, description="Build year"),
        "fuel_type": FieldContract("fuel_type", "string", required=False, description="Primary propulsion fuel type"),
        "service_speed": FieldContract("service_speed", "float", required=True, unit="knots", min_value=3.0, max_value=35.0, description="Laden service speed"),
        "fuel_consumption": FieldContract("fuel_consumption", "float", required=True, unit="MT/day", min_value=1.0, max_value=250.0, description="Daily sea fuel consumption"),
        "availability_date": FieldContract("availability_date", "datetime", required=False, description="Open availability date"),
    },
    freshness_hours_current=720.0,  # 30 days for vessel registry
    freshness_hours_aging=2160.0,
)

PORT_REFERENCE_CONTRACT = DatasetContract(
    dataset_type=DatasetType.PORT_REFERENCE,
    schema_version="1.0.0",
    business_key_fields=("port_id",),
    fields={
        "port_id": FieldContract("port_id", "string", required=True, description="Unique port code"),
        "port_name": FieldContract("port_name", "string", required=True, description="Official port name"),
        "country": FieldContract("country", "string", required=True, description="Country"),
        "latitude": FieldContract("latitude", "float", required=True, min_value=-90.0, max_value=90.0, description="Geographic latitude"),
        "longitude": FieldContract("longitude", "float", required=True, min_value=-180.0, max_value=180.0, description="Geographic longitude"),
        "draft_limit": FieldContract("draft_limit", "float", required=True, unit="meters", min_value=2.0, max_value=35.0, description="Maximum approach draft limit"),
        "berth_limit": FieldContract("berth_limit", "integer", required=False, min_value=1, description="Active terminal berth count"),
        "loading_rate": FieldContract("loading_rate", "float", required=False, unit="MT/day", min_value=100.0, description="Average loading throughput"),
        "discharge_rate": FieldContract("discharge_rate", "float", required=False, unit="MT/day", min_value=100.0, description="Average discharge throughput"),
        "port_cost": FieldContract("port_cost", "float", required=False, min_value=0.0, description="Baseline port call tariff"),
        "currency": FieldContract("currency", "string", required=False, description="Tariff currency denomination"),
    },
    freshness_hours_current=2160.0,  # 90 days for ports
    freshness_hours_aging=4320.0,
)

CARGO_DEMAND_CONTRACT = DatasetContract(
    dataset_type=DatasetType.CARGO_DEMAND,
    schema_version="1.0.0",
    business_key_fields=("cargo_id",),
    fields={
        "cargo_id": FieldContract("cargo_id", "string", required=True, description="Unique cargo requirement identifier"),
        "commodity": FieldContract("commodity", "string", required=True, description="Dry bulk commodity"),
        "quantity": FieldContract("quantity", "float", required=True, unit="MT", min_value=100.0, description="Parcel mass quantity"),
        "origin_port_id": FieldContract("origin_port_id", "string", required=True, description="Load port code"),
        "destination_port_id": FieldContract("destination_port_id", "string", required=True, description="Discharge port code"),
        "laycan_start": FieldContract("laycan_start", "datetime", required=True, description="Opening date of laycan window"),
        "laycan_end": FieldContract("laycan_end", "datetime", required=True, description="Closing date of laycan window"),
        "delivery_deadline": FieldContract("delivery_deadline", "datetime", required=False, description="Latest acceptable discharge date"),
        "freight_rate": FieldContract("freight_rate", "float", required=False, min_value=0.1, description="Indicative freight rate"),
        "currency": FieldContract("currency", "string", required=False, description="Freight contract currency"),
    },
    freshness_hours_current=48.0,
    freshness_hours_aging=168.0,
)

VOYAGE_FIXTURE_CONTRACT = DatasetContract(
    dataset_type=DatasetType.VOYAGE_FIXTURE,
    schema_version="1.0.0",
    business_key_fields=("voyage_id",),
    fields={
        "voyage_id": FieldContract("voyage_id", "string", required=True, description="Charter voyage fixture ID"),
        "vessel_id": FieldContract("vessel_id", "string", required=True, description="Fixed vessel ID"),
        "origin_port_id": FieldContract("origin_port_id", "string", required=True, description="Load port code"),
        "destination_port_id": FieldContract("destination_port_id", "string", required=True, description="Discharge port code"),
        "departure_date": FieldContract("departure_date", "datetime", required=True, description="ATD or planned departure"),
        "arrival_date": FieldContract("arrival_date", "datetime", required=False, description="ATA or estimated arrival"),
        "cargo_id": FieldContract("cargo_id", "string", required=False, description="Laden cargo reference"),
        "freight_rate": FieldContract("freight_rate", "float", required=False, min_value=0.0, description="Fixed voyage freight"),
        "status": FieldContract("status", "string", required=True, description="Voyage execution status"),
    },
    freshness_hours_current=24.0,
    freshness_hours_aging=72.0,
)

BUNKER_SERIES_CONTRACT = DatasetContract(
    dataset_type=DatasetType.BUNKER_SERIES,
    schema_version="1.0.0",
    business_key_fields=("port_id", "fuel_type", "timestamp"),
    fields={
        "port_id": FieldContract("port_id", "string", required=True, description="Bunkering port / hub code"),
        "fuel_type": FieldContract("fuel_type", "string", required=True, description="Fuel grade (VLSFO, MGO, IFO380)"),
        "price": FieldContract("price", "float", required=True, unit="USD/MT", min_value=50.0, max_value=3000.0, description="Spot bunker price"),
        "currency": FieldContract("currency", "string", required=True, description="Bunker quote currency"),
        "timestamp": FieldContract("timestamp", "datetime", required=True, description="Market quote observation time"),
    },
    freshness_hours_current=24.0,  # Bunker prices age rapidly
    freshness_hours_aging=72.0,
)

OPERATIONAL_EVENT_CONTRACT = DatasetContract(
    dataset_type=DatasetType.OPERATIONAL_EVENT,
    schema_version="1.0.0",
    business_key_fields=("event_id",),
    fields={
        "event_id": FieldContract("event_id", "string", required=True, description="Operational event identifier"),
        "vessel_id": FieldContract("vessel_id", "string", required=True, description="Affected vessel ID"),
        "event_type": FieldContract("event_type", "string", required=True, description="Type: WEATHER, CANAL_DELAY, ENGINE_MAINTENANCE"),
        "timestamp": FieldContract("timestamp", "datetime", required=True, description="Event occurrence time"),
        "location": FieldContract("location", "string", required=True, description="Port or sea passage description"),
        "delay_hours": FieldContract("delay_hours", "float", required=False, min_value=0.0, description="Schedule delay duration"),
        "reason": FieldContract("reason", "string", required=False, description="Detailed delay explanation"),
    },
    freshness_hours_current=12.0,
    freshness_hours_aging=48.0,
)

CONTRACT_REGISTRY: Dict[DatasetType, DatasetContract] = {
    DatasetType.VESSEL_MASTER: VESSEL_MASTER_CONTRACT,
    DatasetType.PORT_REFERENCE: PORT_REFERENCE_CONTRACT,
    DatasetType.CARGO_DEMAND: CARGO_DEMAND_CONTRACT,
    DatasetType.VOYAGE_FIXTURE: VOYAGE_FIXTURE_CONTRACT,
    DatasetType.BUNKER_SERIES: BUNKER_SERIES_CONTRACT,
    DatasetType.OPERATIONAL_EVENT: OPERATIONAL_EVENT_CONTRACT,
}


def get_contract(dataset_type: DatasetType | str) -> DatasetContract:
    """Retrieves authoritative dataset contract for a maritime domain."""
    dtype = DatasetType(dataset_type) if isinstance(dataset_type, str) else dataset_type
    if dtype not in CONTRACT_REGISTRY:
        raise ValueError(f"No registered contract for dataset type '{dtype}'")
    return CONTRACT_REGISTRY[dtype]
