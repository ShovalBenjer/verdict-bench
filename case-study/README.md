# Case Study — Account-Review Agent

We run an AI agent that reviews flagged account cases and recommends one of three actions — **APPROVE**, **HOLD**, or **REJECT**. The agent decides by following a plain-text prompt we write. We want a better prompt, and that's your task.

**Write a prompt that decides a case.** Given one case as input, your prompt should make the agent return one of APPROVE / HOLD / REJECT, with its reasoning, by applying the policy in `POLICY.md`.

Use whatever tools you like, including AI (Cursor, Claude, ChatGPT, etc.) — we expect you to, and we'll talk about how you did.

**Up front, so there's no confusion:** you can almost certainly get good answers by dropping this folder into a capable model and telling it to write the prompt. We know — we tried it. That is *not* what we're evaluating, and a polished prompt that scores well earns you little on its own. This job is about how you work *with* AI to improve AI: what you notice, what you question, where you distrust the model and dig in, what you decide and why. That's why the transcript below is required and why we spend the interview on your reasoning, not your final answer. A one-shot "do the assignment" submission is easy to spot and is a weak result here, even when its answers are right.

## What's in the folder

- `POLICY.md` — how our team decides, in plain business terms. **This is your source of truth.**
- `cases/` — flagged cases, one JSON file each.
- `labeled-answers.md` — the expert's decision for a *few* of the cases.

## How we'll score it

We'll run your prompt on the cases in this folder and on other cases as well.

## Deliverables

Bring these to a **30-minute discussion**:

1. Your prompt.
2. A short writeup: the choices you made and why, and how you'd convince yourself the prompt is ready before shipping it.
3. **The complete transcript of how you worked** — every prompt you gave your tools and what came back, in order, including dead ends. Required; a submission without it is incomplete.

## Your prompt's output contract

Your prompt must make the agent return JSON only — first character `{`, last character `}`:

```
{"decision": "APPROVE|HOLD|REJECT", "reasoning": "<why, citing the case>"}
```
