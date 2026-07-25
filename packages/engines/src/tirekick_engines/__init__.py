"""TIREKICK engines.

The laws in docs/LAWS.md are enforced here, not just described there:

- LAW 1 (truth)           models.Finding requires non-empty evidence
- LAW 2 (safety-critical) safety.apply_safety_law clamps locked systems
- LAW 3 (no scrape)       net.ALLOWED_HOSTS
- LAW 4 (eval gate)       registry.FINDING_TYPES[...].enabled_for_paid
- LAW 5 (cogs visible)    cogs.CostMeter
"""

SCHEMA_VERSION = "1.0.0"

__all__ = ["SCHEMA_VERSION"]
