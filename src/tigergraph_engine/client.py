"""
TigerGraph Client interface supporting both Live Savanna/Community clusters and local In-Memory Engine.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from src.config import settings
from src.tigergraph_engine.in_memory_graph import InMemoryTigerGraph

logger = logging.getLogger(__name__)

class TigerGraphClient:
    def __init__(self, data_dir=None):
        self.settings = settings.tg
        self.live_conn = None
        self.local_graph = InMemoryTigerGraph(data_dir)
        self._init_connection()

    def _init_connection(self):
        """Attempts to initialize live pyTigerGraph connection if credentials are configured."""
        if (
            self.settings.host 
            and self.settings.host != "https://savanna.tgcloud.io" 
            and self.settings.password != "tigergraph"
        ):
            try:
                import pyTigerGraph as tg
                self.live_conn = tg.TigerGraphConnection(
                    host=self.settings.host,
                    graphname=self.settings.graph,
                    username=self.settings.username,
                    password=self.settings.password,
                    apiToken=self.settings.api_token
                )
                logger.info("Connected to live TigerGraph cluster at %s", self.settings.host)
            except Exception as e:
                logger.warning("Could not connect to live TigerGraph cluster: %s. Using local engine.", e)
                self.live_conn = None
        else:
            logger.info("Operating in standalone TigerGraph graph mode.")

    def ensure_data_loaded(self):
        if not self.local_graph.is_loaded:
            self.local_graph.load_identities()
            self.local_graph.load_transactions()

    def get_transaction(self, txn_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_data_loaded()
        return self.local_graph.transactions.get(str(txn_id))

    def get_identity(self, txn_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_data_loaded()
        return self.local_graph.devices.get(str(txn_id))

    def get_card_history(self, card_id: str) -> List[Dict[str, Any]]:
        self.ensure_data_loaded()
        return self.local_graph.get_card_history(card_id)

    def get_device_neighbors(self, profile_str: str, exclude_card: Optional[str] = None) -> List[str]:
        self.ensure_data_loaded()
        return self.local_graph.get_device_neighbors(profile_str, exclude_card)

    def detect_card_testing(self, card_id: str, anchor_txn_id: str) -> Tuple[bool, List[str], float]:
        self.ensure_data_loaded()
        return self.local_graph.detect_card_testing(card_id, anchor_txn_id)

    def detect_velocity_structuring(self, card_id: str, anchor_txn_id: str) -> Tuple[bool, List[str], float]:
        self.ensure_data_loaded()
        return self.local_graph.detect_velocity_structuring(card_id, anchor_txn_id)

    def detect_out_of_region(self, card_id: str, txn_id: str) -> Tuple[bool, str, Dict[str, int]]:
        self.ensure_data_loaded()
        return self.local_graph.detect_out_of_region(card_id, txn_id)

    def write_investigation_case(self, case_id: str, case_data: Dict[str, Any]) -> str:
        self.ensure_data_loaded()
        return self.local_graph.write_investigation_case(case_id, case_data)
