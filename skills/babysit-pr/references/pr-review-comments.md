# Addressing PR Review Comments

Workflow for reading, triaging, and fixing review comments while babysitting a PR.

## When to Use This Reference

- Unresolved review threads are present on the PR
- The user asks the babysitter to fix PR comments or review feedback on an existing PR

## Step 1: Get Only Unresolved Threads (GraphQL)

The REST API (`/pulls/{pr}/comments`) returns **all** comments including resolved ones, which wastes context on already-addressed issues. Use the **GraphQL API** instead. It exposes `isResolved` on review threads and lets you skip resolved threads entirely.

**Pagination note:** The queries below use `first: 100`. If `totalCount` in the response exceeds the number of nodes returned, paginate using `pageInfo { hasNextPage endCursor }` and pass `after: "<endCursor>"` on subsequent requests. Most PRs will not hit this limit, but always verify `totalCount` matches.

### Get repo info and PR number

```bash
REPO_WITH_OWNER=$(gh repo view --json nameWithOwner -q .nameWithOwner)
REPO_OWNER=$(echo "$REPO_WITH_OWNER" | cut -d/ -f1)
REPO_NAME=$(echo "$REPO_WITH_OWNER" | cut -d/ -f2)
PR_NUMBER=$(gh pr view --json number -q .number)
```

### Extract unresolved threads

```bash
gh api graphql -f query='
{
  repository(owner: "'"$REPO_OWNER"'", name: "'"$REPO_NAME"'") {
    pullRequest(number: '"$PR_NUMBER"') {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes {
              path
              body
              author { login }
              line
              originalLine
            }
          }
        }
      }
    }
  }
}' 2>&1 | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
threads = data['data']['repository']['pullRequest']['reviewThreads']['nodes']
unresolved = [t for t in threads if not t['isResolved']]
resolved = [t for t in threads if t['isResolved']]
print(f'Total threads: {len(threads)}')
print(f'Resolved: {len(resolved)}')
print(f'Unresolved: {len(unresolved)}')
print()
for i, t in enumerate(unresolved):
    c = t['comments']['nodes'][0]
    user = c['author']['login']
    path = c.get('path', 'N/A')
    line = c.get('line') or c.get('originalLine', '?')
    body_clean = re.sub(r'<!--.*?-->', '', c['body'], flags=re.DOTALL).strip()
    title = 'No title'
    for bline in body_clean.split('\n'):
        bline = bline.strip()
        if bline.startswith('**') or bline.startswith('###'):
            title = re.sub(r'[*#]', '', bline).strip()[:120]
            break
    thread_id = t['id']
    print(f'{i:2d}. {user:40s} {path}:{line}')
    print(f'    {title}')
    print(f'    thread_id: {thread_id}')
    print()
"
```

### Verify the counts

The script prints total, resolved, and unresolved counts. If all threads are resolved, there is nothing to do. Report that to the user and stop.

### Read full bodies of unresolved threads

Once you have the unresolved thread indices, fetch full comment bodies in one shot:

```bash
gh api graphql -f query='
{
  repository(owner: "'"$REPO_OWNER"'", name: "'"$REPO_NAME"'") {
    pullRequest(number: '"$PR_NUMBER"') {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 5) {
            nodes {
              path
              body
              author { login }
              line
              originalLine
              createdAt
            }
          }
        }
      }
    }
  }
}' 2>&1 | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
threads = data['data']['repository']['pullRequest']['reviewThreads']['nodes']
unresolved = [t for t in threads if not t['isResolved']]
for i, t in enumerate(unresolved):
    comments = t['comments']['nodes']
    for j, c in enumerate(comments):
        body = re.sub(r'<!--.*?-->', '', c['body'], flags=re.DOTALL).strip()
        prefix = 'ROOT' if j == 0 else 'REPLY'
        print(f'=== Thread {i}, {prefix} [{c[\"author\"][\"login\"]}] {c.get(\"path\",\"\")}:{c.get(\"line\",\"\")} ===')
        print(body[:2000])
        print()
"
```

## Step 2: Present Options and Get Explicit Consent

After presenting the unresolved thread index, present the deduplicated issue list with your recommended action for each issue. Then stop and get clear feedback from the engineer before you change the PR or mutate GitHub thread state.

- **Default workflow**: Present the unique issues, grouped by duplicates, with the current code context and your recommendation. Ask which issues to fix, reject, or leave alone. Wait for explicit approval, rejection, or modification before making code changes, pushing commits, replying on threads, or resolving threads.
- **Explicit auto-fix exception**: Only skip that consent gate when the user explicitly tells you to auto-fix review comments, for example "auto-fix review comments" or "fix all review comments".

Do not infer consent from a vague request to "handle comments" or similar wording. When the user's intent is ambiguous, ask first.

## Step 3: Deduplicate

Multiple bots often flag the same issue across separate threads. Group unresolved threads by **file + issue description**. Common reviewers:

- `cursor[bot]` — Bugbot
- `devin-ai-integration[bot]` — Devin Review
- `chatgpt-codex-connector[bot]` — Codex

Treat duplicates as a single issue.

## Step 4: Triage Each Issue

For each unique issue, read the **current code** rather than the diff hunk in the comment. The comment may be stale. Then classify:

| Verdict | Action |
|---------|--------|
| **Already fixed** | Note as resolved because the comment was on a prior revision |
| **Valid bug** | Fix it |
| **Valid cleanup** | Fix it |
| **Not applicable** | Explain why |
| **Intentional** | Explain the reasoning |

**Critical:** Bot comments are often filed against earlier revisions. Always verify against the *current* code before acting.

## Step 5: Fix and Commit

- Only act on issues the engineer explicitly approved, unless they explicitly chose the auto-fix exception in Step 2
- Group related fixes into logical commits
- Run type checking and linting after each change
- Commit with a clear message referencing which review comments were addressed
- After the fix is pushed or submitted, resolve the corresponding GitHub review thread(s). If a thread cannot be resolved directly, leave a short reply explaining the fix and mark it as handled in your issue list.

### Resolving a review thread via GraphQL

To resolve a thread, you need its `threadId` (the `id` field from the `reviewThreads` query above). Then run:

```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: { threadId: "THREAD_NODE_ID" }) {
    thread { isResolved }
  }
}'
```

Use this for threads the engineer explicitly agrees are non-actionable or already addressed, not just for threads you fixed with code.

## Step 6: Report to the Engineer

Present a complete table of **every** unresolved thread with the action taken:

```text
| # | Comment | File | Action | Reasoning |
|---|---------|------|--------|-----------|
| 1 | ... | ... | Fixed | ... |
| 2 | ... | ... | Not applicable | ... |
```

The table must account for all unresolved threads from Step 1.
Do not wait until the very end of the babysitting run to reconcile thread state. As each issue is explicitly accepted, rejected, or confirmed as already fixed by the engineer, keep the GitHub thread state aligned with that approved decision by resolving or replying immediately.

## Common Mistakes to Avoid

1. **Using the REST API instead of GraphQL**. The REST API (`/pulls/{pr}/comments`) has no concept of resolved threads. Use the GraphQL `reviewThreads` query with `isResolved`.
2. **Not verifying counts**. If GraphQL reports 5 unresolved threads and your analysis covers 3, you missed 2.
3. **Trusting diff hunks in comments**. Bot comments reference code from review time. Always read the current file.
4. **Presenting false confidence**. If you are not sure you covered everything, say so instead of presenting a partial list as complete.
