"""Medication config loader — single source of truth for med details."""

import json
import os

BOT_DIR = os.getenv("BOT_DIR", os.path.dirname(os.path.abspath(__file__)))

_cache = None


def load_meds():
    """Return the medications list from meds.json (cached after first load)."""
    global _cache
    if _cache is None:
        config_path = os.path.join(BOT_DIR, "meds.json")
        with open(config_path) as f:
            _cache = json.load(f)["medications"]
    return _cache


def find_med_by_content(text):
    """Return the first med whose ``name`` appears in *text*, or None.

    Order in the config file determines match priority — put longer/more-specific
    names first (e.g. "Vitaplex + Neupro 300 units" before "Vitaplex").
    """
    for med in load_meds():
        if med["name"] in text:
            return med
    return None


def reset_cache():
    """Clear the cached config (useful for tests)."""
    global _cache
    _cache = None
