Title: One-click Brownout or unplugged prompt

Labels: enhancement, classifier, ui

## Description

When AC was lost and confidence is low, the classifier sets `prompt` and the question "Brownout or unplugged?". The tray item prints instructions. `brownout-buddy label <id> <answer>` already writes `ground_truth` and does not erase the model label. This issue is the click that calls that same store method.

Estimated effort: about 8 hours.

## Acceptance criteria

- [ ] The tray shows Brownout, Unplugged, and Not sure only when the open sample has `prompt` set.
- [ ] Brownout and Unplugged call `set_ground_truth`. Not sure stores `unknown`.
- [ ] The classifier `label` and `confidence` columns stay as the model wrote them.
- [ ] After an answer, the question is not shown again for that outage.
- [ ] The question is not shown for a pure ISP or LAN outage where AC was not lost.
- [ ] The menu callback does not block the monitor thread.
- [ ] The CLI `label` command still works and remains the fallback when there is no display.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-18-brownout-or-unplugged-prompt
