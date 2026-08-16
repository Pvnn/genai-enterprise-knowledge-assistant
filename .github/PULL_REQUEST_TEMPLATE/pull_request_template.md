## Summary
<!-- What does this PR do? Link to the relevant issue or spec section. -->

## Owner tag
<!-- Which person tag owns the files changed? (P1–P8) -->
- [ ] P1 – Ingestion
- [ ] P2 – DB / Retrieval core
- [ ] P3 – Embeddings / Reranker
- [ ] P4 – Generation / Orchestration
- [ ] P5 – Grounding / Conflict
- [ ] P6 – Auth / Feedback
- [ ] P7 – Frontend Chat UI
- [ ] P8 – Eval

## Definition of Done checklist (Section 12)
- [ ] Only files owned by my tag were created or modified
- [ ] Every public function that other modules call matches its Section 6 signature exactly
- [ ] All structured data uses a Pydantic model (no raw dicts at boundaries)
- [ ] Priority 1 work is complete before any Priority 2 work was attempted
- [ ] Priority 2 code falls back safely to Priority 1 behaviour on error
- [ ] `tenant_id` is threaded through every DB query I touched
- [ ] No hardcoded secrets – everything goes through `config.py`s `Settings`
- [ ] A test file exists or was updated for the new logic
- [ ] `black` / `ruff` checks pass (backend) or `prettier` (frontend)
- [ ] `mypy` reports no new errors (backend)

## Testing
<!-- How was this tested? Which pytest markers/commands were run? -->
```
pytest backend/tests/test_<module>.py -v
```

## Notes for reviewers
<!-- Anything the reviewer needs to know about integration points or fallback behaviour. -->
