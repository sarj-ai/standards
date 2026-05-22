# `no-sequential-await` (`SARJ001`)

> A `for` loop body that `await`s on each iteration serializes I/O that could be parallelized with `asyncio.gather`.

## What it catches

An `await` expression inside the body of a `for`/`while` loop, where the loop is not itself an `async for` (i.e. it's a synchronous iteration over a collection, calling an async function once per element).

## Why we encourage the alternative

CPython's event loop can drive thousands of concurrent network requests. A sequential `await` loop forfeits that capability — each iteration waits for the previous one to finish, so total time is roughly `len(items) × latency_per_request`. The parallel form (`asyncio.gather`) issues all requests up-front, so total time approaches `max(latency_per_request)`.

For network-bound work (HTTP, DB queries, LLM calls, S3) the gap is typically **10–100×** in real workloads. For CPU-bound work the rule is irrelevant — but you shouldn't be using `async` for CPU work either.

The cost of suppressing the rule is real: in a 50-item loop over a 200 ms API call, sequential takes 10 s while parallel takes ~200 ms.

## Bad

```py
async def enrich_users(user_ids: list[str]) -> list[User]:
    users = []
    for uid in user_ids:
        u = await fetch_user(uid)   # serial: 50 IDs × 200ms = 10s
        users.append(u)
    return users
```

## Good

```py
import asyncio

async def enrich_users(user_ids: list[str]) -> list[User]:
    return await asyncio.gather(*(fetch_user(uid) for uid in user_ids))
```

## More examples

**With error handling for partial failures** — `return_exceptions=True`:

```py
results = await asyncio.gather(
    *(fetch_user(uid) for uid in user_ids),
    return_exceptions=True,
)
users = [r for r in results if isinstance(r, User)]
errors = [r for r in results if isinstance(r, Exception)]
```

**With concurrency cap (avoid rate-limit blow-ups)** — use a semaphore:

```py
sem = asyncio.Semaphore(10)

async def _bounded(uid: str) -> User:
    async with sem:
        return await fetch_user(uid)

users = await asyncio.gather(*(_bounded(uid) for uid in user_ids))
```

**Dependent awaits** — where each iteration *needs* the previous result, the rule is a false positive; suppress:

```py
async def follow_chain(start_id: str) -> list[Item]:
    items = []
    current = start_id
    for _ in range(10):
        item = await fetch(current)  # sarj-noqa: SARJ001 — each iteration depends on the prior result's `next_id`
        items.append(item)
        current = item.next_id
    return items
```

## When to suppress

- **Sequential dependency** — each iteration consumes the previous result (see chain example above).
- **Order matters and the operation has side-effects** — e.g. ordered writes where you can't rate-limit fan-out.
- **Hard external rate limit** — but in that case prefer a `Semaphore` over true sequentialization.

Use `# sarj-noqa: SARJ001 — <reason>` inline. The reason is mandatory in code review — reviewers should be able to tell from the comment why the parallel form is wrong.

## References

- [`asyncio.gather`](https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently)
- [`asyncio.Semaphore`](https://docs.python.org/3/library/asyncio-sync.html#semaphore)
- [PEP 492 — coroutines](https://peps.python.org/pep-0492/)
