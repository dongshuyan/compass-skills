"""Compatibility import; implementation ships inside the Codex title plugin."""
from pathlib import Path
import sys
_PLUGIN_SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/clarity-session-titles/scripts'
sys.path.insert(0, str(_PLUGIN_SCRIPTS))
from clarity_rpc import *
