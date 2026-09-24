"""
TigerGraph Model Context Protocol (MCP) Server.
Publishes MCP-compliant tool declarations and exposes execution endpoints.
"""
from typing import Dict, List, Any
from src.tigergraph_mcp.tools import TigerGraphMCPTools

class TigerGraphMCPServer:
    def __init__(self, tools: TigerGraphMCPTools = None):
        self.tools = tools or TigerGraphMCPTools()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns JSON schema definitions of TigerGraph MCP tools for LLM binding."""
        return [
            {
                "name": "tg_get_transaction",
                "description": "Fetch transaction details from the TigerGraph graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "txn_id": {"type": "string", "description": "Transaction ID"}
                    },
                    "required": ["txn_id"]
                }
            },
            {
                "name": "tg_get_identity",
                "description": "Fetch device and connection attributes from identity records.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "txn_id": {"type": "string", "description": "Transaction ID"}
                    },
                    "required": ["txn_id"]
                }
            },
            {
                "name": "tg_get_card_history",
                "description": "Retrieve full transaction history for a card from the graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "card_id": {"type": "string", "description": "Card ID"}
                    },
                    "required": ["card_id"]
                }
            },
            {
                "name": "tg_get_device_neighbors",
                "description": "Traverse the graph to find all other cards sharing a device profile (fraud rings).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "profile_str": {"type": "string", "description": "Device profile string"},
                        "exclude_card": {"type": "string", "description": "Current card ID to exclude"}
                    },
                    "required": ["profile_str"]
                }
            },
            {
                "name": "tg_detect_card_testing",
                "description": "Evaluate transaction history for card testing patterns (Policy R5).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "card_id": {"type": "string", "description": "Card ID"},
                        "anchor_txn_id": {"type": "string", "description": "Flagged transaction ID"}
                    },
                    "required": ["card_id", "anchor_txn_id"]
                }
            },
            {
                "name": "tg_detect_out_of_region",
                "description": "Analyze billing region drift compared to baseline home region (Policy R2/R3).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "card_id": {"type": "string", "description": "Card ID"},
                        "txn_id": {"type": "string", "description": "Flagged transaction ID"}
                    },
                    "required": ["card_id", "txn_id"]
                }
            },
            {
                "name": "tg_find_similar_cases",
                "description": "Query TigerGraph case memory for similar past closed investigations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Fraud pattern"},
                        "card_id": {"type": "string", "description": "Card ID"},
                        "device_str": {"type": "string", "description": "Device description string"},
                        "top_k": {"type": "integer", "description": "Number of cases to retrieve"}
                    }
                }
            },
            {
                "name": "tg_write_case_to_graph",
                "description": "Persist an investigation case and associated edges into the TigerGraph graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string", "description": "Case ID"},
                        "case_data": {"type": "object", "description": "Investigation case record"}
                    },
                    "required": ["case_id", "case_data"]
                }
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes the requested MCP tool."""
        func = getattr(self.tools, tool_name.replace("tg_", ""), None)
        if not func:
            return {"error": f"Tool {tool_name} not found"}
        return func(**arguments)
