# evogate

Agent evolution with a fail closed quality gate. Prompt variants compete on your task suite, only a variant that beats the champion is promoted, and every generation is written to a ledger, kept or rejected, with the reason.

## Why

Letting an agent rewrite its own prompt is easy. Letting it do so safely is the hard part: a new variant can sound better and quietly break the one behavior that matters. evogate treats every variant as untrusted until it proves itself on the same fixed suite the champion passed.

## The gate

A variant is promoted only when both are true:

1. Its total score is strictly higher than the current champion. A tie does not promote.
2. It passes every task marked `critical` in full. A critical failure rejects the variant no matter how high its total score is.

If the runner crashes, times out, or prints nothing, the variant scores zero. The gate fails closed, never open.

## Quick start

```bash
# offline demo, no API key needed
python3 evogate.py demo

# your own tournament
python3 evogate.py run \
  --suite tasks.json \
  --variants variants/ \
  --runner 'python3 my_agent.py "{variant}" "{input}"'

# read the ledger
python3 evogate.py ledger
```

The demo ships a deterministic stand-in agent so the tournament runs offline. It honors directives written in each variant prompt, so you can watch the gate work: the plain variant is rejected for failing a critical task, the grounded variant is promoted with a perfect score, and the verbose variant is rejected because its answer breaks the critical length rule.

```text
gen 1: v1-plain.md score 0.2 -> rejected (critical task(s) failed: short-answer)
gen 2: v2-grounded.md score 1.0 -> promoted (first champion (no incumbent))
gen 3: v3-verbose.md score 0.6 -> rejected (critical task(s) failed: short-answer)
champion: v2-grounded.md (score 1.0)
```

## Task suite format

```json
{
  "name": "my suite",
  "tasks": [
    {
      "id": "short-answer",
      "critical": true,
      "input": "What color is the sky banner? Answer briefly.",
      "checks": {"contains_all": ["teal"], "max_chars": 60}
    }
  ]
}
```

Supported checks: `contains_all`, `contains_any`, `not_contains`, `max_chars`. Tasks marked `critical` must pass completely or the variant is rejected.

## Files it keeps

- `evogate-state.json`: the current champion and its score.
- `evogate-ledger.jsonl`: one line per generation with the variant, its score, the verdict, and the reason. Append only, so the full history of what was rejected and why is never rewritten.

## Tests

```bash
python3 -m unittest discover -s tests
```

12 tests cover the scoring checks, every gate rule including tie and critical failure handling, runner failure scoring zero, and the full demo tournament end to end.

## License

MIT. See [LICENSE](LICENSE).
