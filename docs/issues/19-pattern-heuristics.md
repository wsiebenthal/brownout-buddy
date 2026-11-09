Title: Pattern heuristics from outage history

Labels: enhancement, classifier

## Description

People unplug a laptop at similar times (end of the day, moving rooms) and real brownouts tend to cluster. `PatternSignal` already accepts `ClassifyContext.history` and returns a stub reading that the scorer ignores. Ground truth from the confirmation prompt is the material this should learn from. A habit must not outvote a gateway that is clearly up or clearly down.

Estimated effort: about 18 hours.

## Acceptance criteria

- [ ] Time-of-day rates are computed from rows that have ground truth, not from the model's own labels alone.
- [ ] Several outages in the same short window can raise the brownout side of a low-confidence call.
- [ ] A usual unplug time can raise the unplugged side of a low-confidence call.
- [ ] The pattern reading is ignored when the gateway vote is already enough to publish a label on its own.
- [ ] With no history, the signal stays unavailable and the other rules match version 0.1.
- [ ] The history used for this stays in the local SQLite file and is not uploaded.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-19-pattern-heuristics
