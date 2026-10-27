---
name: be-ambitious
description: Deepen a task without expanding its scope by identifying expert actions, primary material, methods, and independent checks, then rewriting the prompt. Use when the user asks to be ambitious, make a prompt deeper, raise the bar, or invoke this skill.
---

# Be ambitious

Adapted from a prompt shared by Felix Rieseberg (Anthropic):

> I want a deeper version of this task, not a bigger one. Before rewriting it:
> (1) say what a top professional in this field would do here that I'm not
> asking for; (2) name the rawest material they would start from instead of
> what has already been digested for me; (3) name the specific methods and
> tools they would use; (4) say what, other than you or me, would show the
> result is right. Then rewrite my prompt to ask for exactly that.

## Input

The task is whatever follows this skill invocation. Depending on the host, it
may be invoked as `/agent-skills:be-ambitious`, `/be-ambitious`, from a skill
picker, or through a natural-language request. If nothing follows, use the
user's most recent request in this conversation. If there is none, ask for the
task in one line and stop.

## Deeper, not bigger

Keep the user's goal and scope. Depth means a higher standard for the same
outcome: better sources, sharper methods, and real verification. Do not add
deliverables, features, or side quests. If a suggestion would make the job
larger rather than better, drop it.

## Steps

Name the field first (for example, "investigative journalism," "SRE incident
response," or "clinical pharmacology"), then answer the four questions for
that field. Be concrete: name the actual thing, not the category.

1. **What a top professional would do that wasn't asked for.** Name two or
   three moves that separate expert work from competent work here. Examples
   include stating the decision the work serves, checking base rates,
   reproducing before fixing, or writing the counter-argument.
2. **The rawest material.** Name the primary sources to start from instead of
   summaries: the dataset, not the chart; the filing, not the article; the logs
   and code, not the bug report; the paper's methods section, not the abstract.
   Say where the material lives if you know.
3. **Specific methods and tools.** Name techniques, instruments, libraries,
   commands, or frameworks, and say why each fits the task.
4. **What, other than the user or the model, would show it is right.** Name an
   external check, such as a test suite or benchmark, a reproduction,
   ground-truth data, a known answer, a measurement, a domain expert or
   reviewer, or real user behavior. Say what result would pass and what would
   fail.

If you don't know enough about the field to answer, say so. Do not invent a
source or tool.

## Rewrite

Write the rewritten prompt in one fenced block the user can copy. Ask for
exactly what the four answers describe: start from the raw material, use the
named methods, and finish with the external check and its pass criterion. Keep
it as long as needed and in the user's voice.

Stop after the rewrite. Offer in one line to run it now. Do not start the task
unless the user says so.
