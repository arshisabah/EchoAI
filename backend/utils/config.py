import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN", "")
DEVICE = "cuda" if os.getenv("USE_CUDA", "false").lower() == "true" else "cpu"
