# AI-Powered Python Test Generator

A developer tool that turns Python source code into a runnable pytest suite.
Paste or upload a module and it analyzes the code, generates tests, executes
them, and reports line coverage - optionally using an AI provider to write the
tests, with a deterministic generator as the fallback.

## Features

- **Static analysis** of module-level functions with Python's `ast`: branches,
  loops, printed output, raised errors, `async def`, defaults and annotations
- **Rule-based test generation** that picks inputs which will not trip the code
  under test - no `0` for divisors, no negatives for validated parameters, dict
  shapes inferred from subscripts, and parameter types inferred from how the
  body uses them when annotations are absent
- **Optional AI generation** via mock / OpenAI / Gemini / Claude / DeepSeek,
  validated before use and falling back to the rule-based generator on any
  failure (missing key, network error, non-code answer, code that will not parse)
- **Scenario coverage**: branches, loops, `pytest.raises` for validation errors,
  `capsys` for printed output, `asyncio.run` for coroutines
- **Test execution and line coverage** through coverage.py, with an HTML report
- **Streamlit UI** with a code editor, a loadable example, per-run metrics
  (tests, passed, coverage, generation mode) and downloadable test files

## How it works

```
source.py
   │
   ├─ analyzer/          ast → FunctionInfo (branches, loops, prints, raises, async)
   ├─ test_generator/    FunctionInfo → test plan → pytest source (+ AI prompt)
   ├─ llm/               optional provider call, validated & fenced-code stripped
   └─ cov_tools/         coverage run / report / html in a child process
```

When AI generation is used its output is shown and downloadable, but **coverage
is always measured with the deterministic rule-based tests**, so an unreliable
model answer cannot distort the metric.

## Requirements

- Python 3.11+
- pip

Provider SDKs in `requirements.txt` are optional; the `mock` provider needs none
of them.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### API keys (optional)

Copy the template and fill in only the providers you use:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`secrets.toml` is git-ignored. Keys can also be typed into the sidebar at
runtime; a key found in secrets takes precedence.

## Screenshots

Screenshots are not committed. To produce the three the README expects, run the
app, load the example, click **Analyze & Generate Tests**, and capture:

| File | What to capture |
| --- | --- |
| `docs/screenshots/01-main.png` | The main screen with code in the editor and the sidebar visible |
| `docs/screenshots/02-generated-tests.png` | The **Generated tests** tab showing the produced pytest file |
| `docs/screenshots/03-coverage.png` | The **Coverage** tab with the percentage and the coverage.py report |

Then reference them here with `![Main screen](docs/screenshots/01-main.png)`.

## Running

Start the UI:

```bash
streamlit run src/web/app.py
```

Then: paste code (or click **Load example**), or upload a `.py` file, and press
**Analyze & Generate Tests**. Results appear on the right as a metric row plus
three tabs - **Analysis**, **Generated tests** and **Coverage**. Generated tests
can be downloaded from the Generated tests tab. **Advanced → Clean temp files &
reports** removes the scratch modules, uploads, generated test files and the
HTML report.

Or run the same pipeline from the command line:

```bash
python src/main.py
```

```bash
python src/main.py path/to/your_module.py
```

## Running the generated tests manually

Generated tests are skipped unless `RUN_UI_GENERATED=1` is set, so a normal
`pytest` run only executes the project's own suite:

```bash
pytest
```

```bash
RUN_UI_GENERATED=1 pytest tests/generated -q
```

Coverage by hand:

```bash
python -m coverage run --source=data/sample_code -m pytest tests/generated -q
```

```bash
python -m coverage report -m
```

```bash
python -m coverage html
```

## Layout

| Path | Contents |
| --- | --- |
| `src/analyzer/` | AST parsing and function metadata |
| `src/test_generator/` | Test plan, AI prompt, rule-based pytest emitter |
| `src/llm/` | Provider adapters and the fallback-safe service |
| `src/cov_tools/` | coverage.py driver |
| `src/web/` | Streamlit UI and its presentation helpers |
| `data/sample_code/example.py` | Bundled sample target |
| `tests/` | The project's own test suite |
| `tests/generated/` | Generated output (git-ignored) |

## Known limitations

- **Only module-level functions.** Class methods and nested functions are
  skipped, because generated tests import functions by name.
- **The target module is imported and its tests are executed locally.** Top-level
  side effects in the analyzed file will run. Only feed it code you trust.
- Rule-based assertions are structural (`result is not None`); they prove the
  code runs on a given input, not that its output is correct. Concrete value
  assertions are what the AI path is for.
- When AI generation is used, the AI suite is what you see and download, but
  coverage is measured with the deterministic rule-based suite so an unreliable
  answer cannot distort the metric. Both files are downloadable.
- Default model ids may drift; override them in the sidebar's **Model** field.
