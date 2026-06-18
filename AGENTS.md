# Agent Instructions — TutorAI (Socratic Tutor)

## Project context
TutorAI is a Socratic tutoring assistant for school subjects, built by a
2nd-year bachillerato student learning Python. The primary audience for this
codebase is the student themself — code is a learning artifact, not just a
working product.

## Top priority: simplicity over cleverness
- Always choose the simplest solution that works, even if a more "elegant"
  or "professional" pattern exists. Boring, obvious code wins.
- Prefer plain Python (functions, basic classes, dicts, lists) over design
  patterns, abstract base classes, metaclasses, decorators-for-decorators'-
  sake, or other advanced features unless there is no reasonable simpler way.
- Do not introduce layers of abstraction (interfaces, factories, dependency
  injection, plugin systems) for a project this size. One clear way to do
  things beats a flexible framework nobody asked for.
- A flat, easy-to-follow script or small set of modules is better than a
  deeply nested package structure.

## Minimum libraries
- Use Python's standard library first. Only reach for a third-party package
  when the standard library genuinely cannot do the job reasonably.
- Before adding any dependency, ask: "Is this truly necessary?" If the
  answer is unclear, leave it out.
- Avoid heavy frameworks (e.g. full web frameworks, ORMs, agent
  orchestration frameworks) unless explicitly requested. A small number of
  well-known, lightweight libraries (e.g. `requests`, the official `openai`
  or `anthropic` SDK for the tutor's LLM calls) is acceptable when the task
  genuinely needs it — but never add a library "just in case."
- Every new dependency must be justified in the PR/commit description: what
  it's for and why the stdlib wasn't enough.

## Code style for a beginner audience
- Write code as if explaining it to a student with limited coding
  experience. Favor readability over brevity or performance tricks.
- Use clear, descriptive variable and function names. Avoid single-letter
  names except for trivial loop counters.
- Keep functions short and focused on one task. If a function is hard to
  summarize in one sentence, split it up.
- Avoid "clever" one-liners (nested comprehensions, chained ternaries,
  walrus operator gymnastics, obscure unpacking) — write the obvious
  multi-line version instead.
- Use plain `if`/`for`/`while` control flow rather than functional-style
  tricks (`map`/`filter`/`reduce`, complex generator pipelines) unless it
  makes the code clearly simpler.
- Add type hints and short docstrings only where they genuinely help
  understanding — don't over-annotate trivial code.
- Comments should explain *why*, not *what*. Skip comments that just
  restate what the code obviously does.

## Socratic tutor behavior
- The tutor must follow Socratic method principles: guide the student with
  questions rather than handing out direct answers. Keep this logic
  explicit and easy to read/modify (e.g. clear prompt templates, simple
  state tracking of the conversation) rather than buried in clever
  abstractions.
- Prompts and subject logic should be easy for the student to find, read,
  and tweak themselves.

## When in doubt
- If there's a tradeoff between "more correct/robust" and "much simpler to
  understand," lean toward simple, and leave a short note (comment or PR
  description) about the tradeoff so the student can revisit it later.
- Don't add error handling, configuration options, or extensibility hooks
  for situations that aren't actually happening yet.
