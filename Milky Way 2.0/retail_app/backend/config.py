"""Load only supported settings from a local, ignored .env file. Never execute it."""
import os
from pathlib import Path

def load_settings():
    path=Path(__file__).resolve().parents[1]/'.env'
    if not path.is_file():return
    allowed={'OPENAI_API_KEY','OPENAI_MODEL','RETAIL_DB','RETAIL_STATE_DIR'}
    for raw in path.read_text().splitlines():
        raw=raw.strip()
        if not raw or raw.startswith('#') or '=' not in raw:continue
        key,value=raw.split('=',1);key=key.strip();value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
        if key in allowed and value:os.environ.setdefault(key,value)
load_settings()
