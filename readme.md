# TestGen - AI-Powered Python Test Generator

A developer tool that turns Python source into a runnable pytest suite. Paste or
upload a module and TestGen analyzes it, generates tests, executes them, and
reports statement coverage - with optional AI assistance on top of a
deterministic generator that always runs.

## Features

- **Static analysis** of module-level functions with Python's `ast`: branches,
  loops, printed output, raised errors, `async def`, defaults and annotations
- **Deterministic generation** that picks inputs which will not trip the code
  under test - no `0` for divisors, no negatives for validated parameters, dict
  shapes inferred from subscripts, and parameter types inferred from how the
  body uses them when annotations are absent
- **AI-assisted generation** as an additive second suite, validated before it is
  shown, with automatic fallback when a provider is unavailable
- **Scenario coverage**: branches, loops, `pytest.raises` for validation errors,
  `capsys` for printed output, `asyncio.run` for coroutines
- **Test execution and statement coverage** through pytest and coverage.py, with
  pass/fail counts, per-file figures and an HTML report
- **Dark developer UI** with a code editor, loadable samples, a workflow
  indicator, and downloadable test files

## Deterministic vs AI-assisted

| | Deterministic | AI assisted |
| --- | --- | --- |
| Source | AST analysis + rules | Language model, prompted with the plan and the function bodies |
| Repeatable | Yes | No |
| Needs network / API key | No | Yes (except the `mock` provider) |
| Executed by the app | **Yes** | No - shown and downloadable only |
| Counted in coverage | Yes | No |

AI mode does not replace deterministic generation: both suites are produced and
presented in tabs. The deterministic suite is the one written to
`tests/generated/`, executed, and measured, so an unreliable model answer can
neither distort the coverage number nor run in your environment. If the provider
fails for any reason - missing key, network error, non-code answer, code that
does not parse - the app says so plainly and you still get the deterministic
tests.

## Supported providers

| Provider | Key (secret name) | Notes |
| --- | --- | --- |
| `mock` | none | Local stub, useful for demos and tests |
| `openai` | `OPENAI_API_KEY` | Custom base URL supported |
| `gemini` | `GEMINI_API_KEY` | |
| `claude` | `ANTHROPIC_API_KEY` | |
| `deepseek` | `DEEPSEEK_API_KEY` | OpenAI-compatible endpoint |

Default model ids may drift; override them in the **Model** field.

## Requirements

- Python 3.11+
- pip

Provider SDKs in `requirements.txt` are optional - the `mock` provider needs
none of them.

## Setup

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

On macOS/Linux activate with `source .venv/bin/activate` instead.

### Configuration

API keys are read from `.streamlit/secrets.toml`, which is git-ignored:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Fill in only the providers you use. A key can also be typed into the panel at
runtime; it is held in the session only, never written to disk, echoed back, or
logged. A key found in secrets takes precedence.

Optional environment variables:

| Variable | Effect |
| --- | --- |
| `TESTGEN_REPO_URL` | Shows a repository link in the application header |

## Running

```bash
streamlit run src/web/app.py
```

### Workflow

`Source -> Analyze -> Generate -> Run -> Coverage`

1. Paste code, click a sample button, or upload a `.py` file.
2. Pick **Deterministic** or **AI Assisted** in the configuration panel.
3. Press **Analyze & Generate Tests** to see the analysis, detected structure
   and generated suite.
4. Press **Run Tests** to execute them and produce the coverage report.
5. Download the generated `.py` from the Generated Tests section.

Editing the source marks existing results as stale rather than silently leaving
mismatched data on screen; re-run to refresh them.

### Command line

The same pipeline, without the UI:

```bash
python src/main.py
```

```bash
python src/main.py path/to/your_module.py
```

## Screenshots

Screenshots are not committed. To capture the three the README references, run
the app, click the **Calculator** sample, then **Analyze & Generate Tests**, then
**Run Tests**:

| Path | What to capture |
| --- | --- |
| `docs/screenshots/01-main.png` | Header, editor with code, configuration panel and analysis summary |
| `docs/screenshots/02-generated-tests.png` | The Generated Tests section with the deterministic/AI tabs |
| `docs/screenshots/03-coverage.png` | Test execution counts beside the coverage report |

Then reference them here, for example `![Main workspace](docs/screenshots/01-main.png)`.

## Running the generated tests manually

Generated tests are skipped unless `RUN_UI_GENERATED=1` is set, so a normal
`pytest` run only executes the project's own suite:

```bash
pytest
```

```bash
RUN_UI_GENERATED=1 pytest tests/generated -q
```

## Layout

| Path | Contents |
| --- | --- |
| `src/analyzer/` | AST parsing and function metadata |
| `src/test_generator/` | Test plan, AI prompt, deterministic pytest emitter |
| `src/llm/` | Provider adapters and the fallback-safe service |
| `src/cov_tools/` | coverage.py driver and result parsing |
| `src/web/app.py` | Streamlit entry point (orchestration only) |
| `src/web/pipeline.py` | Backend glue: staging, analysis, generation, execution |
| `src/web/components/` | One module per UI panel |
| `src/web/styles.py` | The single stylesheet |
| `src/web/state.py` | Session state and staleness handling |
| `data/sample_code/example.py` | Bundled sample target for the CLI |
| `tests/` | The project's own test suite |
| `tests/generated/` | Generated output (git-ignored) |

## Known limitations

- **Only module-level functions.** Class methods and nested functions are
  skipped, because generated tests import functions by name. The UI says so when
  it happens.
- **The analyzed module is imported and the deterministic suite is executed
  locally.** Top-level side effects in the analyzed file will run. Only analyze
  code you trust. AI-generated code is never executed.
- **Statement coverage only.** Branch coverage is not measured and is not
  reported.
- Deterministic assertions are structural (`result is not None`); they prove the
  code runs on a given input, not that its output is correct. Concrete value
  assertions are what the AI path is for.
