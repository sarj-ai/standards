# `inefficient-string-concat-in-loop` (`SARJ002`)

> `s += "..."` inside a `for` or `while` loop is O(n²) in CPython. Append to a list and `"".join(...)` once at the end for O(n).

## What it catches

An `AugAssign` (`+=`) whose right-hand side is string-shaped (`str` literal, f-string, `str(x)` call, `repr(x)`, `format(...)` result, or a `+` chain that's string-shaped) inside the body of a `for`/`while`.

## Why we encourage the alternative

Python strings are immutable. Each `s += "x"` allocates a fresh string and copies the entire previous content. Across n iterations that's `1 + 2 + 3 + ... + n` characters copied — O(n²) total work. For 1k iterations it's a million unnecessary character copies; at 100k iterations the code goes from interactive (0.05s) to noticeable (5s+).

CPython has a clever optimization that *sometimes* mutates the string in place when the refcount is exactly 1, but the optimization is fragile — it breaks under `f-string` interpolation, multi-threaded interpreters (Python 3.13+ free-threaded), and any aliasing. Relying on it is a bet that doesn't pay off.

The idiomatic fix is **collect-then-join**:

```py
parts = []
for x in items:
    parts.append(f"row {x}")
result = "".join(parts)
```

`str.join` allocates exactly one output string of known size. The work is O(n).

## Bad

```py
def render(items: list[str]) -> str:
    s = ""
    for x in items:
        s += f"row {x}\n"
    return s
```

## Good — list + join

```py
def render(items: list[str]) -> str:
    parts: list[str] = []
    for x in items:
        parts.append(f"row {x}\n")
    return "".join(parts)
```

## More examples

**Comprehension + join** — same idea, idiomatic one-liner:

```py
def render(items: list[str]) -> str:
    return "".join(f"row {x}\n" for x in items)
```

**`io.StringIO`** — preferred when the producer doesn't naturally yield individual strings:

```py
import io

def render(rows: Iterable[Row]) -> str:
    buf = io.StringIO()
    for r in rows:
        buf.write(r.to_csv_line())
        buf.write("\n")
    return buf.getvalue()
```

**Integer accumulator** — *not* flagged (the rule looks at string-shaped RHS only):

```py
total = 0
for x in numbers:
    total += x   # SARJ002 does not fire here
```

## When to suppress

- **Very short loops** where the constant factor doesn't matter (n < 100) AND the code is more readable as `+=`. The rule is intentionally pure-mechanical, so it'll fire on these — suppress with reasoning:

```py
s = ""
for col, val in row.items():
    s += f"{col}={val} "  # sarj-noqa: SARJ002 — n < 10 columns, readability > theoretical O(n²)
```

- **Templating that mutates an existing prefix** — unusual; usually rewriting around `str.format`/`f-string` makes the rule moot.

## References

- [Python wiki — performance tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [`str.join`](https://docs.python.org/3/library/stdtypes.html#str.join)
- [`io.StringIO`](https://docs.python.org/3/library/io.html#io.StringIO)
