"""Context engineering helpers for grounded, tool-aware LLM prompts."""

from __future__ import annotations

from typing import Any


class ContextEngine:
    """Assemble structured context for better instruction following and retrieval grounding."""

    def build(
        self,
        *,
        user_message: str,
        system_prompt: str,
        history_summary: str | None = None,
        tool_catalog: str | None = None,
        retrieved_documents: list[dict[str, Any]] | None = None,
    ) -> str:
        """Return a grounded prompt with the user goal, conversation memory, and evidence."""
        sections: list[str] = [
            "System instructions:",
            system_prompt.strip() or "You are a helpful assistant.",
            "",
            "User goal:",
            user_message.strip() or "No explicit user goal was provided.",
        ]

        if history_summary:
            sections.extend(["", "Conversation memory:", history_summary.strip()])

        if tool_catalog:
            sections.extend(["", "Tool context:", tool_catalog.strip()])

        evidence = retrieved_documents or []
        if evidence:
            sections.extend(["", "Grounding evidence:"])
            for item in evidence:
                title = str(item.get("filename") or item.get("document_id") or "document")
                text = str(item.get("text") or "").strip()
                if text:
                    sections.append(f"- {title}: {text}")

        return "\n".join(sections).strip()
