"""Pydantic model for the assembled risk memo."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class RiskMemo(BaseModel):
    concept_summary: str
    season: str

    # Memo sections (Markdown text)
    relevant_rule_text: str = ""
    relevant_precedent: str = ""
    technical_facts: str = ""
    arguments_for: str = ""
    arguments_against: str = ""
    political_protest_media_risk: str = ""
    mitigations: str = ""
    bottom_line: str = ""
    recommended_action: str = ""
    open_questions: str = ""
    debate_transcript: str = ""

    def to_markdown(self) -> str:
        sections = [
            f"# Regulatory Risk Memo\n**Concept:** {self.concept_summary}  \n"
            f"**Season:** {self.season}",
            "---",
            f"## 1. Relevant Rule Text\n{self.relevant_rule_text}",
            f"## 2. Relevant Precedent\n{self.relevant_precedent}",
            f"## 3. Technical Facts That Matter\n{self.technical_facts}",
            f"## 4. Arguments for Legality\n*The following section is advocacy, not factual synthesis.*\n\n{self.arguments_for}",
            f"## 5. Arguments Against Legality\n*The following section is advocacy, not factual synthesis.*\n\n{self.arguments_against}",
            f"## 6. Political, Protest, and Media Risk\n{self.political_protest_media_risk}",
            f"## 7. Mitigations\n{self.mitigations}",
            f"## 8. Bottom Line\n{self.bottom_line}",
            f"## 9. Recommended Next Action\n{self.recommended_action}",
            f"## 10. Open Questions\n{self.open_questions}",
        ]
        if self.debate_transcript:
            sections.append(f"---\n## Appendix — Debate Transcript\n{self.debate_transcript}")
        return "\n\n".join(s for s in sections if s.strip())
