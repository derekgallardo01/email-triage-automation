"""Reply drafter - generates a draft reply from a per-class template.

Templates live in prompts/<class_name>.txt. Each one is a Python
str.format template that takes:
  - {sender_name}: first-name greeting
  - {subject}: the original subject (for context lines)
  - {body_excerpt}: first ~200 chars of the inbound body

The drafter has two backends. The default substitution backend literally
fills in the template - deterministic, no API call. The LLM backend
passes the template + inbound email to Claude as a system prompt + user
message and gets back a more contextual draft.

The shape returned is the same either way - a DraftedReply with subject,
body, and a confidence score (used for "send vs queue for review"
downstream).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .parser import Email


@dataclass
class DraftedReply:
    """A draft reply to an inbound email."""
    in_reply_to_message_id: str
    subject: str
    body: str
    backend: str
    confidence: float  # caller decides whether to auto-send or queue
    error: str | None = None


class Drafter:
    """Generates draft replies based on a per-class template."""

    def __init__(
        self,
        prompts_dir: Path | str | None = None,
        backend: str | None = None,
    ):
        self.prompts_dir = Path(prompts_dir) if prompts_dir else _default_prompts_dir()
        self.backend = backend or os.environ.get("EMAIL_TRIAGE_LLM", "substitution")

    def draft(self, email: Email, class_name: str) -> DraftedReply | None:
        """Generate a draft reply for the given class, or None if no template."""
        template_path = self.prompts_dir / f"{class_name}.txt"
        if not template_path.exists():
            return None
        template = template_path.read_text(encoding="utf-8")
        try:
            if self.backend == "claude":
                body = self._draft_claude(email, class_name, template)
                backend_used = "claude"
                confidence = 0.85  # caller's threshold for auto-send
            else:
                body = self._draft_substitution(email, template)
                backend_used = "substitution"
                # Substitution is deterministic; confidence reflects template
                # quality. 0.7 by default - good enough for human review,
                # not high enough for auto-send without oversight.
                confidence = 0.7
            return DraftedReply(
                in_reply_to_message_id=email.message_id,
                subject=f"Re: {email.subject}",
                body=body,
                backend=backend_used,
                confidence=confidence,
            )
        except Exception as ex:
            return DraftedReply(
                in_reply_to_message_id=email.message_id,
                subject=f"Re: {email.subject}",
                body="",
                backend=self.backend,
                confidence=0.0,
                error=str(ex),
            )

    # ----- The backend seam -----------------------------------------------

    def _draft_substitution(self, email: Email, template: str) -> str:
        first_name = email.sender_name.split()[0] if email.sender_name else "there"
        body_excerpt = email.body_text.strip().replace("\n", " ")[:200]
        return template.format(
            sender_name=first_name,
            subject=email.subject,
            body_excerpt=body_excerpt,
        )

    def _draft_claude(self, email: Email, class_name: str, template: str) -> str:
        """Production swap point.

        Implementation sketch:

            from anthropic import Anthropic
            client = Anthropic()
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                system=("You write reply drafts for an SMB support team. "
                        f"This email was classified as '{class_name}'. "
                        "Use the template below as a guide but adapt to the "
                        "actual content of the email. Stay polite and concise."),
                messages=[{"role": "user",
                           "content": f"Template:\\n{template}\\n\\nInbound email:\\n"
                                       f"From: {email.sender_name}\\n"
                                       f"Subject: {email.subject}\\n\\n"
                                       f"{email.body_text}"}],
            )
            return response.content[0].text

        Until wired, fall back to substitution so the kit still runs.
        """
        return self._draft_substitution(email, template)


def _default_prompts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts"
