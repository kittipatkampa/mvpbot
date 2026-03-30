"""Canned demo response for the magic query "demo!".

Edit DEMO_PARTS below to customize what the demo shows.
Each entry is streamed as a separate SSE part in order:
  - type "reasoning": rendered as a collapsible section with the given label
  - type "text":      rendered as the main assistant answer (full markdown)

Content is streamed word-by-word to simulate a real LLM response.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

# ---------------------------------------------------------------------------
# Customise the demo here
# ---------------------------------------------------------------------------

DEMO_PARTS: list[dict] = [
    # ── Opening reasoning block ────────────────────────────────────────────
    {
        "type": "reasoning",
        "label": "demo",
        "content": "user wants me to show all possible display I can do",
    },
    # ── Welcome text ───────────────────────────────────────────────────────
    {
        "type": "text",
        "content": """\
# 👋 Display Demo

This response was generated **entirely without an LLM** — it's a canned showcase \
of every rich display feature supported by this UI.

> Type `demo!` any time to see this again.

---
""",
    },
    # ── Reasoning: thinking about formatting ──────────────────────────────
    {
        "type": "reasoning",
        "label": "Thinking about formatting",
        "content": """\
I should demonstrate headings, lists, blockquotes, bold, italic, \
inline code, and links before moving on to tables and math.
""",
    },
    # ── Text: typography ──────────────────────────────────────────────────
    {
        "type": "text",
        "content": """\
## Typography

You can use **bold**, *italic*, ~~strikethrough~~, and `inline code`.

### Blockquote

> "Any sufficiently advanced technology is indistinguishable from magic."
> — Arthur C. Clarke

### Lists

Unordered:

- 🚀 Streaming SSE responses
- 🧠 Extended thinking with collapsible sections
- 📐 Math rendering via KaTeX
- 📊 GFM tables

Ordered:

1. User sends a message
2. Backend classifies intent
3. Agent thinks and responds
4. UI streams tokens in real time

### Links

Visit the [assistant-ui docs](https://www.assistant-ui.com/) for more.

---
""",
    },
    # ── Reasoning: thinking about code ────────────────────────────────────
    {
        "type": "reasoning",
        "label": "Thinking about code blocks",
        "content": "I'll show fenced code blocks with different languages next.",
    },
    # ── Text: code blocks ─────────────────────────────────────────────────
    {
        "type": "text",
        "content": """\
## Code Blocks

Python:

```python
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print([fibonacci(i) for i in range(10)])
# [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

Bash:

```bash
cd backend
uv run uvicorn assistant_service.main:app --reload --port 8000
```

JSON:

```json
{
  "type": "reasoning",
  "label": "Query intent",
  "content": "Intent: general"
}
```

---
""",
    },
    # ── Reasoning: thinking about tables ──────────────────────────────────
    {
        "type": "reasoning",
        "label": "Thinking about tables",
        "content": "GFM tables are supported via remark-gfm. I'll show a feature comparison table.",
    },
    # ── Text: tables ──────────────────────────────────────────────────────
    {
        "type": "text",
        "content": """\
## Tables

| Feature | Supported | Notes |
|---------|:---------:|-------|
| GFM tables | ✅ | `remark-gfm` |
| Math (KaTeX) | ✅ | `remark-math` + `rehype-katex` |
| Code blocks | ✅ | Language label + copy button |
| Emojis | ✅ | Plain Unicode |
| Strikethrough | ✅ | GFM |
| Task lists | ✅ | GFM |
| Mermaid diagrams | ❌ | Not installed |
| Syntax highlighting | ❌ | No highlighter configured |

### Task list (GFM)

- [x] Streaming SSE backend
- [x] Multi-label reasoning sections
- [x] Rich markdown rendering
- [ ] Mermaid support *(not yet)*

---
""",
    },
    # ── Reasoning: thinking about math ────────────────────────────────────
    {
        "type": "reasoning",
        "label": "Thinking about math",
        "content": """\
KaTeX is available. I'll show inline math and a display equation — \
something visually impressive like the Fourier transform or Euler's identity.
""",
    },
    # ── Text: math ────────────────────────────────────────────────────────
    {
        "type": "text",
        "content": """\
## Math (KaTeX)

Inline math: The quadratic formula is $x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$.

Display math — Euler's identity:

$$e^{i\\pi} + 1 = 0$$

The Fourier transform:

$$\\hat{f}(\\xi) = \\int_{-\\infty}^{\\infty} f(x)\\, e^{-2\\pi i x \\xi}\\, dx$$

Bayes' theorem:

$$P(A \\mid B) = \\frac{P(B \\mid A)\\, P(A)}{P(B)}$$

---
""",
    },
    # ── Closing text ──────────────────────────────────────────────────────
    {
        "type": "text",
        "content": """\
## That's the full demo! 🎉

To customise what appears here, edit `DEMO_PARTS` in \
`backend/src/assistant_service/demo_response.py`.
""",
    },
]

# ---------------------------------------------------------------------------
# Streaming generator — no need to edit below this line
# ---------------------------------------------------------------------------

CHUNK_SIZE = 4  # characters per SSE token event


async def stream_demo() -> AsyncGenerator[str, None]:
    """Yield SSE events for the demo response, simulating token streaming."""
    for part in DEMO_PARTS:
        part_type = part["type"]
        content: str = part["content"]
        label: str | None = part.get("label")

        # Stream the content in small chunks to mimic LLM token streaming
        for i in range(0, len(content), CHUNK_SIZE):
            chunk = content[i : i + CHUNK_SIZE]
            if part_type == "reasoning":
                event = {"type": "reasoning", "content": chunk, "label": label}
            else:
                event = {"type": "token", "content": chunk}
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.008)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
