# Personal Job Search Assistant

A local CLI and Streamlit workspace for comparing job descriptions with a master resume, drafting from existing facts, and tracking jobs in SQLite. Optional OpenAI API suggestions identify relevant resume paragraphs and possible gaps.

## Current status

Implemented: rule-based analysis, a searchable job inbox, web-assisted official/visa evidence checks, requirement-level API analysis, source-linked bullet generation with independent fact checks, version review, SQLite tracking, and budget records.

Scheduling, account registration and automatic applications are not enabled. The planned schedule is weekdays at 09:00 America/New_York. The computer must be running for this local UI; an API key does not host the application. See [WORKFLOW.md](WORKFLOW.md).

## Setup

Use Python 3.11+ for the full application, including TOML key configuration. The CLI uses the standard library; the UI requires Streamlit.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
New-Item -ItemType Directory -Force private
Copy-Item examples/resume.txt private/master_resume.txt
```

The example resume is fictional. Replace it with your own facts before analyzing real opportunities. Keep personal files in `private/`, which is excluded from Git.

## Streamlit

```powershell
powershell -ExecutionPolicy Bypass -File .\run-ui.ps1
```

Open http://127.0.0.1:8502. Keep the terminal open; Ctrl+C stops the server. If the port is occupied, select a different port with `run-ui.ps1 -Port 8503`, or run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8503
```

- **Analyze a job:** paste text or upload UTF-8 TXT/MD, optionally override metadata, then analyze and save.
- **Job inbox:** search, inspect requirements and gaps, and generate tailored bullets (instructions below).
- **Job tracker:** filter records, inspect evidence, and edit status and notes.
- **Master resume:** inspect source paragraphs and SHA-256.
- **Agent settings and trial:** check key availability and cost estimates, generate API suggestions, and download saved results.

Set the master resume path in the sidebar. DOCX, TXT, and Markdown are supported. Loading the fictional example does not save anything until you click Analyze. Each explicit analysis creates a new record; reruns and downloads do not. Metadata overrides take precedence over JD labels.

The UI binds to loopback, disables Streamlit usage statistics, and limits uploads to 5 MB. It is not configured for public hosting. Rule-based analysis stays local; explicit API generation sends extracted resume text and the JD to OpenAI.

## CLI

```powershell
python main.py analyze examples/job_description.txt --resume examples/resume.txt
python main.py analyze private/job.txt --resume private/master_resume.txt --json
python main.py analyze private/job.txt --company "Example" --job-title "Data Analyst" --location "New York, NY" --work-mode "Hybrid" --salary '$110,000 base'
python main.py list --status NEW
python main.py show 1
python main.py update 1 --status REVIEWED --notes "Confirm hybrid schedule"
python main.py update 1 --status APPLIED --notes "Submitted manually"
python main.py --db private/jobs.sqlite3 list
```

The default source is `private/Master Resume.docx` when present, otherwise `private/master_resume.txt`. Override with `JOB_ASSISTANT_RESUME`, `--resume`, or the UI sidebar. `--db` belongs before the subcommand. `--output-dir` selects an output directory. `run.ps1` uses Python on PATH or a bundled local runtime when available. Common input errors return exit code 2; success returns 0.

Recommended JD labels are `Company:`, `Job title:`, `Job URL:`, `Location:`, `Work mode:`, and `Base salary:`. Unlabeled metadata is not guessed. Parsing targets English text. URLs and PDF job descriptions are not fetched or parsed.

## Reports and tracker

Each run writes a unique output directory with `analysis.md`, `analysis.json`, `tailored_resume.md`, and `job_description.txt`. JSON includes original source paragraphs, SHA-256, and the draft paragraph mapping.

The SQLite jobs table stores company, job title, URL, date found, salary, location, match score, status, notes, resume path, analysis path, and analysis JSON. UI and CLI share `data/jobs.sqlite3`. Manual CLI analyses create separate history. Inbox discovery deduplicates by posting URL or company/title/location (or requisition when available); imperfect source identities may still produce duplicates. Salary text is not normalized.

## Job inbox workflow

1. Put the master resume at `private/Master Resume.docx`, or change its path in the sidebar. Configure the API key as described below.
2. Open **Job inbox** and click **Search recent jobs**. This searches public indexed LinkedIn, Indeed and Built In NYC postings from the last seven days. Inspect source coverage and exclusions: it is bounded search, not exhaustive scraping or a logged-in feed. Unknown dates stay unverified.
3. Select **Open job**. The first tab shows requirements, links, date evidence, salary and eligibility restrictions. Use **Verify official posting and visa evidence** to request a separate web-assisted report. Historical sponsorship does not establish this role's eligibility; unknowns remain pending.
4. In **Matches, gaps and changes**, click **Analyze requirements and gaps**. Each requirement has a strong/partial/gap/unknown assessment, original resume evidence and a suggested action. The API evidence score weights required items 2 and preferred items 1, with strong=1, partial=0.5 and missing/unknown=0. It is separate from the legacy keyword score in Job tracker.
5. In **Tailored bullets**, optionally enter revision instructions and click **Generate tailored bullets**. One click makes two bounded API calls: drafting and independent factual checking. Review original and suggested wording side by side. Unsupported audited rewrites revert to the original; invalid metrics or known technologies stop generation. These checks reduce errors but do not prove factual correctness.
6. Approve a version only after reading it, or regenerate with feedback. Download the Markdown draft. Each bullet retains its original role and source ID. Approval does not apply for a job. Changes to the resume or JD make old versions stale and block approval.

Retrieved descriptions may be summaries. Paste the full JD in the first tab for complete analysis. Unknown sponsorship is never labeled eligible. Salary below target and onsite work are preferences to review, not automatic exclusions. Search and API buttons run only when explicitly clicked; page reruns do not incur another call. Saved results survive server restarts.

Statuses: NEW, REVIEWED, READY_TO_APPLY, APPLIED, INTERVIEW, REJECTED, SKIPPED. Status changes are bookkeeping and never submit an application. Updating notes replaces previous notes.

## Evidence and integrity

The master resume is the only source of experience facts. Preferences do not establish skills or achievements. Never invent experience, technologies, metrics, titles, responsibilities, or accomplishments.

The score is keyword evidence coverage, not hiring probability or an ATS score:

1. Recognize a controlled list of concepts; repeated concepts count once.
2. Project evidence scores 1; skills/summary mentions or ambiguous requirements score 0.5; no evidence scores 0.
3. General requirements weigh 2; preferred requirements weigh 1. Higher-weight mentions win; equal-weight ambiguity is handled conservatively.
4. Score is rounded 100 times weighted evidence divided by total weight. No recognized requirements gives 0 with a review warning.
5. Scores of at least 60 recommend manual review. All results still require judgment.

Unparsed requirements are excluded, so scores can be inflated. Keyword matching cannot reliably interpret negation, alternatives, seniority, tenure, degrees, or visa rules. The tool does not calculate years of experience. Similar technologies are not interchangeable. Location, hybrid, and salary preferences are separate from skills scoring.

Drafts reorder contiguous colon-led experience bullets within their original role, preserving all original paragraphs, employers, titles, dates, and metrics. Unrecognized formats retain their order. DOCX extraction reads ordinary body paragraphs, tabs, and table text, not full layout, headers, footers, graphics, or hyperlink targets. Markdown drafts are review artifacts, not polished submission documents.

## Optional OpenAI API

Create a key in the [API dashboard](https://platform.openai.com/api-keys). Never send it in chat or commit it. Recommended temporary PowerShell configuration:

```powershell
$secureKey = Read-Host 'OpenAI API key' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
.\run-ui.ps1
```

Stop any old UI instance and restart from this terminal. Alternatively, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in OPENAI_API_KEY. This file is ignored by Git but remains plaintext and may be synchronized by cloud-folder software.

The adapter uses gpt-5.4-mini through Responses with structured output and store=false; this does not promise zero provider retention. It selects source paragraph IDs, explains emphasis, and suggests gaps/questions. The program validates IDs and supplies original text. Model explanations can still be incorrect. Suggestions do not alter your resume, rule-based score, or application status.

Budgets in agent-config.json default to $1/day and $20/month using New York dates. SQLite atomically reserves $0.10 per ordinary request or $0.25 per search request. Returned usage replaces the reservation with an estimate at $0.75/million input tokens, $4.50/million output tokens and $0.01 per web search call, ignoring cache discounts. Rates were checked October 1, 2026; update the code if they change. Inbox requests cap input at 60,000 UTF-8 bytes, output at 6,000 tokens and search at three calls. The older trial caps input at 40,000 bytes and output at 4,000 tokens. Requests are not automatically retried.

Failed or interrupted requests retain their reservation until manually reconciled. A reservation is not proof of a charge. Budgets cover this tool/database only, not other account activity. Compare estimates with provider billing. Suggestions and usage persist in api_runs. Missing credentials disable generation; mocked tests do not validate live connectivity, access, or model quality.

References: [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini). The previous Ollama adapter remains in code but is not used by the UI.

## Architecture and tests

- main.py / job_assistant/cli.py: CLI commands.
- app.py: Streamlit UI.
- job_assistant/service.py: shared reports and persistence.
- job_assistant/resume.py: source extraction and conservative drafting.
- job_assistant/analysis.py: keyword evidence and scoring.
- job_assistant/tracker.py: SQLite jobs.
- job_assistant/api_model.py: OpenAI calls and budget ledger.
- job_assistant/workspace.py / workspace_ui.py: discovery, evidence analysis, eligibility reports and versioned bullet review.
- job_assistant/local_model.py: optional unused Ollama adapter.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use fictional facts and temporary databases. API responses are mocked; tests incur no model charges. No vector database or agent framework is required.

## Privacy and backups

Git excludes personal resumes/PDFs, private inputs, generated output, databases, environment files, API secrets, and virtual environments. Keep personal input in private/. Local files may still be synchronized by OneDrive or similar software. Back up your resume, database, and outputs together; stored output paths are absolute and may need adjustment after a move. Existing private historical records remain as originally generated; English source code does not retroactively rewrite them.
