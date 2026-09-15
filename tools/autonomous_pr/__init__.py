"""Minimal local AUTONOMOUS_PR execution harness (TSK-0026).

Execution mechanics only. The governing contracts are:

- ``AGENTS.md``, section "Change authorisation and diff review" — the
  authoritative governance/authorization contract for ``AUTONOMOUS_PR``.
- ``docs/AUTONOMOUS_PR_HARNESS.md`` — the subordinate execution-mechanics
  contract this package implements.

Nothing in this package grants, infers, or originates ``AUTONOMOUS_PR``
authorization. A task identifier accepted by this package is execution
input only, never evidence of user authorization.
"""
