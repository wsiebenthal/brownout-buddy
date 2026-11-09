"""Ground-truth question.

The one-click tray prompt is not implemented. :class:`StubConfirmationPrompt`
returns no answer and explains the command that stores one. Persistence
lives on :meth:`brownout_buddy.store.OutageStore.set_ground_truth`.
"""

from __future__ import annotations

from brownout_buddy.classifier.types import Classification


class StubConfirmationPrompt:
    """Stand-in for the tray question. ``ask`` always returns None."""

    def ask(
        self, classification: Classification, outage_ids: list[int]
    ) -> str | None:
        del classification, outage_ids
        return None

    @staticmethod
    def menu_text(classification: Classification, outage_ids: list[int]) -> str:
        first = str(outage_ids[0]) if outage_ids else "<id>"
        question = classification.question or "Brownout or unplugged?"
        return (
            f"{question} The one-click tray prompt is not implemented yet. "
            f"Classifier label is {classification.label.value} "
            f"(confidence {classification.confidence:.2f}). "
            f"Save an answer with `brownout-buddy label {first} brownout` "
            "(or unplugged, isp-outage, unknown). "
            "That answer is stored as ground truth and does not erase the "
            "classifier label."
        )
