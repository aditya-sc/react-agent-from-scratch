# NOTES — ReAct Agent From Scratch (Project 0)

A study reference built from the process of writing this project. Goal of the
project: build the **Thought → Action → Observation** agent loop with **zero
frameworks** (raw model API only) so LangChain/LangGraph stop feeling like magic.

---

## 1. Architecture (what each file does)

| File | Responsibility |
| --- | --- |
| `model.py` | `get_model()` + `LLMModel.chat()` — the thin model client (the swap point) |
| `tools.py` | `ToolRegistry` + the actual tool functions, registered at import time |
| `prompt.py` | `system_prompt()` — builds the ReAct instructions + few-shot example |
| `agent.py` | `call_agent()` — the loop: prompt → parse → call tool → feed observation → repeat |
| `main.py` | entry point, wires it together |

**Mental map from LangChain/LangGraph:**
- `ChatOllama` / `ChatOpenAI` → my `get_model()`
- `@tool` / tool binding → my `ToolRegistry`
- `StateGraph` / nodes / edges → a plain `for` loop with a max-iterations guard
- `AgentExecutor` / ReAct agent → my Thought/Action/Observation loop
- output parsers → my regex parsing of the reply

---

## 2. The model client (`get_model`)

- **Thin on purpose.** It's just the *swap point*, not a "gateway." No retries, no
  routing, no fallbacks — those are Layer-6 production concerns added later.
- Targets Ollama's **OpenAI-compatible endpoint**: `http://localhost:11434/v1/chat/completions`.
  Keeping the request OpenAI-shaped means swapping to Groq/OpenRouter/Gemini later is
  just a base-URL + key change — same code. (The native `ollama` SDK would lock the
  code to Ollama's API shape.)
- `get_model()` is a **factory function** returning an `LLMModel` instance.

### Response structure (OpenAI-compatible)
```json
{
  "choices": [{ "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop" }],
  "usage": {"prompt_tokens": 36, "completion_tokens": 8, "total_tokens": 44}
}
```
- Answer lives at `["choices"][0]["message"]["content"]`.
- `finish_reason: "stop"` = ended naturally; `"length"` = hit token cap.
- `usage` = token counts (watch for cost / context budget).

---

## 3. `requests` quick reference (bridged from Go/C#)

```python
resp = requests.post(url, json=payload)   # json= serializes the dict AND sets Content-Type
resp.raise_for_status()                    # throws on 4xx/5xx (like EnsureSuccessStatusCode)
data = resp.json()                         # parses body into a plain dict/list (NOT a typed object)
resp = requests.get(url, params={...})     # params= builds the ?query=string for you
```
- No manual `JsonSerializer` / `json.Marshal` — `json=` does it.
- Errors don't throw by default — call `raise_for_status()` explicitly.
- **Debug trick:** when `.json()` fails with `Expecting value: line 1 column 1`,
  the response wasn't JSON (usually an HTML page). `print(resp.text[:200])` to see it.
  → Caused by hitting a *website* (`coingecko.com`) instead of its *API*
  (`api.coingecko.com/api/v3/...`).

---

## 4. Python idioms learned (coming from Go/C#/JS)

- **Classes:** `__init__` is the constructor; `self` is explicit (like Go's receiver,
  not C#'s implicit `this`); no field declarations — fields exist once assigned on
  `self`; no `new` keyword; no `public/private` (leading `_` = "private by convention").
- **Type hints:** use builtin generics lowercase — `list[dict]`, not `typing.List[...]`.
- **Spread is `*`, not `...`** — `[*old_list, new_item]`. JS's `...` is Python's
  literal `Ellipsis` object (a real gotcha). Or just `list.append(x)`.
- **`**` unpacks a dict into kwargs:** `fn(**{"a": 1})` == `fn(a=1)`. Don't write
  `**kwargs=...` — that's a syntax error; `**` already names it.
- **`json.loads` vs `json.load`:** `loads` parses a **s**tring; `load` parses a file.
  The model returns a string → `json.loads`.
- **f-string braces:** inside an f-string, `{{` and `}}` produce a *literal* brace
  (needed when the text contains JSON). In a **normal** string they stay `{{` literally —
  don't double them there.
- **Raw strings for regex:** prefix with `r"..."` so `\s` etc. aren't mangled.
- **Iterating a dict** yields **keys**, not pairs. Use `.items()` for `name, value`.
- **Importing:** any top-level name in a module is importable; nothing special needed
  to "expose" it. Build shared state (like the populated `registry`) once at module
  bottom so it runs at import time and all importers share it.

---

## 5. Tool registry design

- Registry = a dict: `name -> {"fn": callable, "description": str}`.
- **Functions carry their own metadata** — `register(fn)` can pull `fn.__name__` and
  `fn.__doc__` (the docstring) off the function. No need to pass name/description.
- Tools take args and return a string/JSON observation.
- `call(name, **kwargs)` looks up `["fn"]` and calls it: `self._tools[name]["fn"](**kwargs)`.
- (Optional: make `register` a decorator — like C# attributes — by `return fn` at the end.)

---

## 6. Prompt engineering (the agent's control logic)

In a ReAct agent **the prompt IS the control flow** — it matters more here than anywhere.
Four layers of enforcing the output format, weakest → strongest:

1. **Show the exact template** in a delimited block (not buried in prose).
2. **State hard rules:** "Output EXACTLY one Thought + Action + Action Input, then STOP.
   Do NOT write Observation yourself — it will be given to you."
3. **Few-shot example** — one *complete* mini-episode, including the `Observation:` line
   so the model learns it's *input it receives*, not output it writes. Use a *different*
   example than the real question so the model generalizes instead of copying.
4. **Stop sequence (strongest, API-level):** pass `"stop": ["Observation:"]` in the
   payload so the model is physically cut off before it can hallucinate a fake tool
   result. This is the trick that makes text-ReAct reliable with small local models.

- **Role** sets behavior, not flavor: "You answer ONLY by calling tools, never from
  memory" pushes the model to actually use tools.
- The question goes as a **user** message; the instructions are the **system** message.
- Learn more: Anthropic interactive prompt tutorial (github.com/anthropics/prompt-eng-interactive-tutorial)
  + the original ReAct paper's prompt appendix. Best teacher: run it, watch it break
  format, tighten the prompt.

---

## 7. The agent loop (`call_agent`)

Algorithm:
```
messages = [system: system_prompt(tools), user: question]
client = get_model()                       # create ONCE, outside the loop
for _ in range(max_iters):                 # the forever-loop guard
    reply = client.chat(messages)

    if Final Answer in reply: return it     # stop condition

    parse Action + Action Input
    try:
        args = json.loads(action_input)     # str -> dict
        observation = registry.call(action, **args)
    except Exception as e:
        observation = f"Error: {e}"         # tool errors don't crash the loop

    messages.append(assistant: reply)        # <-- MUST feed both back, or the loop
    messages.append(user: f"Observation: {observation}")  #     re-sends identical msgs forever
return "Stopped: reached max iterations."    # give-up after the loop
```

### Parsing: string-split vs regex
- String: `reply.split("Action:", 1)[1].split("\n")[0].strip()` — simple but fragile.
- **Regex (cleaner):**
  ```python
  re.search(r"Action:\s*(.+)", reply)               # rest of the line ('.' stops at \n)
  re.search(r"Action Input:\s*(.+)", reply)
  re.search(r"Final Answer:\s*(.*)", reply, re.DOTALL)  # DOTALL = '.' also matches \n (multiline answer)
  ```
  `\s*` absorbs whitespace after the colon; guard `if match:` before `.group(1)`
  (search returns `None` on no match). `re.search` finds anywhere; `re.match` only anchors at start.

---

## 8. Bugs I hit (and the lesson each taught)

| Bug | Lesson |
| --- | --- |
| `-> List[]` syntax error | Use builtin `list[dict]`, lowercase, no import |
| `_message_reducer(self, ...)` called bare | Call methods via `self.method(...)`; never pass `self` by hand |
| `[..., new_message]` | `...` is `Ellipsis`, not JS spread — use `*` or `.append` |
| Posting to `/v1` (no path) | OpenAI chat endpoint is `/v1/chat/completions` |
| `["bitcoin"]["usd"]` hardcoded | Use the args (`[crypto_id][currency]`) so the tool generalizes |
| `coingecko.com` → `.json()` crash | Hit the **API** host, not the website; HTML isn't JSON |
| `**kwargs=json.loads(...)` | `**` already unpacks — write `**json.loads(...)` |
| `registry.call(name, json.loads(...))` positional | Splat the dict: `call(name, **args)` |
| `prompt.system_prompt` used as a value | It's a **function** — call it: `system_prompt(registry.describe())` |
| Never appended reply/observation to messages | The loop re-sent identical messages → never progressed |
| Regex computed but old split still used | Wiring something in ≠ writing it next to the old code — replace it |

---

## 9. "Done when" checklist (Project 0)

- [ ] Solves a genuine **2–3 step** task (e.g. "compare bitcoin and ethereum price" → two tool calls)
- [ ] Handles a **tool error** without crashing (e.g. "price of fakecoin123" → 404 → recovers)
- [ ] I can **explain every line cold** (stop sequence, growing messages, `**json.loads`, regex groups)

## 10. Deliberately out of scope (do later)
- Multi-provider routing / retries in `get_model()` (grows in later projects)
- Native tool-calling JSON format (optional second pass after text ReAct works)
- Any LangChain / LangGraph import
