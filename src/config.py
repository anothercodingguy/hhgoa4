"""
Configuration module for TigerGraph Agentic Fraud Investigation System (HHGOA 2026).
"""
import os
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "HHGOA_IEEE"
CASES_DIR = BASE_DIR / "cases"

class TigerGraphSettings(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("TG_HOST", "https://savanna.tgcloud.io"))
    graph: str = Field(default_factory=lambda: os.getenv("TG_GRAPH", "FraudGraph"))
    username: str = Field(default_factory=lambda: os.getenv("TG_USERNAME", "tigergraph"))
    password: str = Field(default_factory=lambda: os.getenv("TG_PASSWORD", "tigergraph"))
    secret: str = Field(default_factory=lambda: os.getenv("TG_SECRET", ""))
    api_token: str = Field(default_factory=lambda: os.getenv("TG_TOKEN", ""))
    use_in_memory_fallback: bool = Field(default=True)

class AgentSettings(BaseModel):
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))
    llm_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("OPENAI_API_KEY", "")))
    llm_model: str = Field(default="gemini-2.0-flash")
    temperature: float = 0.1
    max_tokens: int = 4096
    
    # Policy Thresholds from Bank Fraud Policy v1.0
    weak_signal_max_prob: float = 0.70     # Rule R1
    case_creation_min_prob: float = 0.30   # Section 3a
    sar_filing_min_exposure: float = 1000.0# Section 3a & Rule R2
    uncertain_escalate_exposure: float = 500.0 # Rule R8
    block_card_l1_max_exposure: float = 2500.0 # Approval routing L1 vs L2
    card_testing_max_auth: float = 5.0     # Pattern 1
    stop_high_confidence: float = 0.85     # Section 6
    stop_low_confidence: float = 0.15      # Section 6

class Settings(BaseModel):
    tg: TigerGraphSettings = TigerGraphSettings()
    agent: AgentSettings = AgentSettings()
    data_dir: Path = DATA_DIR
    cases_dir: Path = CASES_DIR

settings = Settings()
