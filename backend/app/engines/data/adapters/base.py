"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Data Source Adapter Abstraction & Air-Gap Compliance Interface
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class DataSourceAdapter(ABC):
    """Abstract base class for controlled, air-gapped data ingestion adapters."""

    @abstractmethod
    def extract_raw_records(
        self, source_payload: Any, **kwargs: Any
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extracts raw record dictionaries and provenance metadata from input.
        Returns:
            Tuple of (records_list, provenance_metadata_dict)
        """
        pass


class FutureLiveApiAdapter(DataSourceAdapter):
    """
    Non-active stub for future live external API sources.
    Strictly disabled per air-gap architecture requirements.
    """

    def extract_raw_records(
        self, source_payload: Any, **kwargs: Any
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        raise NotImplementedError(
            "Air-gap architecture violation: Live API network ingestion is strictly disabled in VesselOptima. "
            "All datasets must be ingested via air-gapped local file exports."
        )
