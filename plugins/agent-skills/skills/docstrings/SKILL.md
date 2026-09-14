---
name: docstrings
owner: corey.katzburg@ofbasis.com
description: >
  Use when the user invokes /docstrings; asks to explain or improve a specific
  confusing comment or docstring; asks to write, update, review, or audit
  comments or docstrings; or explicitly includes comments or docstrings in
  general documentation work. For targeted requests, investigate the related
  code and explain the named comment or docstring or, when edits are requested,
  rewrite it clearly following the guidelines and instructions in this skill.
  For broader requests, audit the requested code for missing documentation
  around complex or non-obvious behavior; confusing,
  vague, jargon-heavy, incomplete, or overly detailed explanations; unfamiliar
  concepts that are not defined; missing purpose, contracts, side effects,
  returns, or exceptions; and redundant documentation that merely repeats the
  code. The result should be clear, easy to understand, and quick to read
  to someone who has never seen the related code or system.
  Comments default to 1-3 lines and docstrings to 1-8 lines, preferring
  shorter.
---

# Docstrings

Write comments and docstrings that explain complex code clearly to a reader who has never seen the code or system. Preserve code behavior unless the user separately asks for a behavior change.

## Keep them short

Docstrings should be clear and easily understandable, and part of that is being able to read them quickly. Most comments by default should be 1-3 lines and docstrings should be 1-8 lines, preferring shorter as better. They should only go over this amount if there is genuinely enough very important information that a reader should know that cant fit in that content.

`Args`, `Returns`, and `Raises` sections do not count toward the line limit. Include them on function docstrings unless every argument, return, and exception is obvious, for example `is_feature_flag_enabled(feature_flag: str) -> bool` when the function does not raise.

## Prepare

1. Read the documented code, its types, representative callers, and relevant tests before judging the documentation. Investigate only as far as needed to verify the code's purpose and contract.
2. For conditional behavior, inspect every branch that changes persisted state,
   return behavior, queue acknowledgement or retry behavior, ownership of later
   work, or caller-visible errors. State the exact condition and outcome instead
   of broadening a branch-specific rule.
3. Read the repository's docstring or documentation guidance when available. In Arnold, read `.agents/skills/documentation/references/writing-good-docstrings.md`. Follow repository guidance when it conflicts with this skill.
4. Follow the user's requested mode:
   - **Explain, review, or audit:** Return an explanation or findings without editing files.
   - **Write, update, improve, rewrite, or fix:** Make focused documentation-only edits.

Do not infer edit permission from the skill invocation alone.

## Decide What Needs Documentation

Strongly favor a docstring when a function, class, or module has a complex or non-obvious purpose, contract, invariant, filtering rule, side effect, failure condition, validation rule, or interaction with another system. Omit a docstring only when the name, signature, types, and surrounding code fully explain the contract and added text would merely repeat the code.

Use docstrings to explain the documented object's purpose and externally meaningful behavior. Use inline comments to explain non-obvious local reasoning or constraints. Do not narrate assignments, function calls, or control flow.

For broad audits, prioritize:

1. Incorrect or stale documentation that disagrees with the code.
2. Complex or non-obvious behavior with no useful documentation.
3. Unfamiliar technical, project, or domain terms that are not defined in ordinary language.
4. Missing purpose, contracts, invariants, side effects, return behavior, or caller-relevant exceptions.
5. Vague, jargon-heavy, confusing, incomplete, redundant, or unnecessarily long writing.
6. `Args`, `Returns`, or `Raises` sections that repeat names and types without explaining meaning.

If confusing code needs clearer naming or structure instead of more documentation, report that separately. Do not hide a design problem behind a long docstring or change the code unless the user asks.

## Write Clearly

- Define unfamiliar concepts in ordinary language.
- Explain what the code does and why it exists when those facts are not already clear.
- Document arguments by their meaning and effect, not by repeating names and types.
- Describe return values, exclusions that prevent likely misunderstandings, caller-relevant exceptions, side effects, and important optional-versus-required behavior when relevant.
- For functions with several meaningful parameters, cross-component side
  effects, or deliberate failure behavior, include `Args`, `Returns`, and
  `Raises` unless every argument, return, and exception is obvious. Follow
  the language and repository's established format. These sections do not
  count toward the 1-8 line default.
- Add an example only when it makes non-obvious calculations, filtering, or state changes materially easier to understand.
- Include only the information needed to understand or safely use the code. Remove repetition and implementation narration.
- State uncertainty when the code and tests do not establish intent. Do not invent a stronger contract than the implementation supports.

Before finalizing, ask:

> Could a reader who has never seen this code or the system it belongs to explain every technical term, what the code does, and why it exists? Could they read it in 30 seconds or less and completely understand it?

For a multi-component workflow, also ask:

> Could that reader identify which component acts, what exact record or message
> changes, under what condition, what happens next, which component continues
> the work, and what failures reach the caller?

## Explain Queued and Multi-Component Workflows

When code coordinates asynchronous jobs, queues, concurrent work, or multiple systems:

- Name each participating system or execution path at first use. Replace umbrella phrases such as "either queue system" with the actual alternatives.
- Describe behavior the documented function guarantees or intentionally
  delegates, including persisted state changes. Do not compress several steps
  into an umbrella label.
- Explain guaranteed ordering and name the component responsible for each action. Do not invent a total order for work that may run concurrently.
- Define queue terms by their verified observable effect. For example, when the
  queue client implements acknowledgement by deleting an SQS message, explain
  that a successful acknowledgement deletes the message from the queue.
- Distinguish accepting or scheduling work from finishing it. State whether the
  current function waits, returns, or leaves another worker responsible for
  completion.
- When the documented function participates in follow-up work, name the
  component that records the need for that work, the condition that causes
  publication, and the worker that receives it next.
- For an `ExceptionGroup`, describe every intentionally grouped error and the
  operation that produced it. If the concrete exception classes vary, use
  meaningful code names such as `execution_error` and `follow_up_error` instead
  of inventing narrower types.

## Quality Target

This docstring is vague because it assumes the reader already understands NetSuite records, its metadata catalog, and why Basis checks it:

```python
"""Validate selected native write operations from a metadata-catalog OpenAPI body.

Args:
    metadata_catalog: Raw OpenAPI metadata-catalog response to validate.
    vola_id: Vendor organization linked account ID.
    record_types: NetSuite REST record types whose operations are checked.
    accounting_book_id: Optional accounting book ID.
    firm_id: Optional firm ID.

Returns:
    None.

Raises:
    NetSuiteApiException: If the metadata catalog is malformed.
    NetSuiteApiAuthException: If a required permission is missing.
"""
```

Rewrite it by defining the unfamiliar concepts first, explaining why the check exists, and documenting each value by its meaning:

```python
"""Check which NetSuite write operations are available to the connected role.

NetSuite represents business objects such as journal entries, vendor bills,
vendors, and customers as records. Its metadata catalog is a JSON document
describing the record types and actions available to the authenticated role.
This function checks that document without creating or changing customer data.

Basis must be able to create every required record type. For transaction
records, Basis must also be able to update an existing record so it can write
configured audit fields. Missing required access fails validation. Missing
optional access is logged without failing validation.

Args:
    metadata_catalog: JSON response from NetSuite describing the record types
        and actions available to the connected role.
    vola_id: ID of the Basis NetSuite connection, included in validation logs.
    record_types: Names of the NetSuite business objects to check, such as
        `journalEntry`, `vendorBill`, or `vendor`.
    accounting_book_id: ID of the Basis book, included in optional-access
        warning logs when available.
    firm_id: ID of the Basis firm, included in optional-access warning logs
        when available.

Returns:
    None if every required action is available. Missing optional actions are
    logged without failing validation.

Raises:
    NetSuiteApiException: If NetSuite's response is not a valid metadata
        catalog.
    NetSuiteApiAuthException: If the connected role cannot perform a required
        create or update action.
"""
```

Use the example as a clarity standard, not as a required length or template. The body is longer than the 1-8 line default because it carries important information that cannot fit shorter. The `Args`, `Returns`, and `Raises` sections do not count toward that limit. Prefer the short default whenever that extra body detail is not needed.

### Queued Workflow Example

This is an illustrative workflow, not documentation of the current Google Drive implementation.

This version hides the systems, timing, state changes, and failure sources behind vague phrases:

```python
"""Run a file sync through either queue system.

Uses the request ID as the VendorRun ID, removes the message after the work is
accepted, and schedules another run if another request is combined with the
running sync.

Raises:
    ExceptionGroup: If both operations fail.
"""
```

Name the execution paths, conditions, state changes, actors, and grouped errors:

```python
"""Run one file sync through the legacy VendorRunQueue or durable SQS path.

Legacy jobs pass ``legacy_queue_id`` and ``legacy_queue_version`` so this
function can mark that queue entry complete or failed. Durable SQS jobs pass
``request_id``. When no VendorRun for the same connection is active or pending,
the sync creates a new VendorRun with ``id=request_id``. An SQS redelivery can
then find that same record instead of creating duplicate work. A webhook job
may pass ``skip_if_synced_after``. The sync skips work when a successful sync
completed at or after that time and already finished linking the files.

After durable execution accepts the job, the SQS worker acknowledges the
message. A successful acknowledgement deletes it from the queue. The worker
does not wait for the sync to finish. If another request arrives while a sync
for the same connection is running, this function creates one PENDING VendorRun
when none exists or reuses the existing PENDING run. The pending run represents
the need for another sync. After the running sync finishes or fails, this
function publishes a new SQS message for the pending sync so another worker can
receive it and start the next sync.

Args:
    connection_id: ID of the file-storage connection to synchronize.
    legacy_queue_id: ID of the legacy queue entry whose outcome this function
        reports. Used with ``legacy_queue_version``.
    legacy_queue_version: Expected version of the legacy queue entry.
    request_id: Stable ID from the durable SQS request. When no VendorRun for
        the same connection is active or pending, the new VendorRun uses this
        ID so a redelivery can find the same work.
    skip_if_synced_after: Webhook request time. The sync is skipped when a
        successful sync completed at or after this time and finished linking
        the files.

Returns:
    None.

Raises:
    ExceptionGroup: Contains both ``execution_error``, the error that caused
        the current sync to fail, and ``follow_up_error``, an error while
        checking for or publishing a pending follow-up SQS message.
    Exception: Re-raises the original sync error when follow-up checking
        succeeds, or propagates a follow-up publication error after a
        successful sync.
"""
```

The example describes observable behavior at the function boundary. It does not narrate each internal call. The body is longer than the default because a queued multi-system contract often cannot fit in 8 lines. Use that length only when the extra information is genuinely required. The `Args`, `Returns`, and `Raises` sections do not count toward the limit.

## Finish

1. Verify every documentation claim against the current code and tests.
2. Confirm comments are 1-3 lines and the docstring body is 1-8 lines unless the extra length is justified. `Args`, `Returns`, and `Raises` do not count toward that limit.
3. Make no behavior changes unless the user requested them.
4. For edits, run narrow formatting, lint, or documentation checks for the changed files. If no automated check applies, review the diff manually.
5. Report what was explained, reviewed, or changed; what was verified; and any documentation gaps left intentionally.
