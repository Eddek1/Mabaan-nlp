from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW       = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_LEXICON   = PROJECT_ROOT / "data" / "lexicon"
DATA_BIBLE     = PROJECT_ROOT / "data" / "bible"
DATA_LABELLING = PROJECT_ROOT / "data" / "labelling"

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-opus-4-8"
LLM_MAX_TOKENS = 8096

# Pipeline
BATCH_SIZE = 20          # entries processed per LLM call
CACHE_ENABLED = True     # use prompt caching for the Recipe system prompt

# Supported input formats
SUPPORTED_EXTENSIONS = {".txt", ".csv", ".json", ".tsv"}
