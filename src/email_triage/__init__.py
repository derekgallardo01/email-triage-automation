"""Email triage automation - parse, classify, route, draft.

Default LLM backend is deterministic stub so the kit runs anywhere
without keys. Set EMAIL_TRIAGE_LLM=claude (with ANTHROPIC_API_KEY) to
route through Claude for reply drafting.
"""
__version__ = "1.0.0"
