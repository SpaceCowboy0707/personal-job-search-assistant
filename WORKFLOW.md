# Agent Workflow Roadmap

## Status

Implemented: CLI/Streamlit analysis, manual bounded public-web discovery, pending/excluded job inbox, web-assisted official/visa reports, requirement-level evidence analysis, source-linked bullet generation and fact checks, version review, SQLite tracking and budget checks. Live calls require a configured key. Scheduling, registration and submission are not enabled. Web reports require human source review; they do not establish visa eligibility.

The expanded scope supersedes the initial V1 restriction on application automation. Current code still submits nothing.

## Intended flow

1. Run discovery weekdays at 09:00 America/New_York independently of the UI. The machine must be awake and online; catch-up runs must avoid duplicates.
2. Discover full-time roles posted, updated, or reposted within seven days on LinkedIn, Indeed, and Built In NYC. Employer sites verify discovered jobs only. Report access failures and incomplete coverage; never claim exhaustive coverage.
3. Deduplicate by employer, title, location, and official requisition. Label reposts and historical updates; do not repeatedly apply.
4. Assess skills, direction, visa evidence, and preferences independently. Exclude explicit sponsorship prohibitions. Place unverified eligibility in a separate queue.
5. Show recommendations, unverified roles, and exclusions with evidence links in Streamlit. The user selects jobs for tailoring.
6. Generate versioned drafts from master-resume facts with source references, diffs, and judgment questions. Accept user revisions without inventing experience.
7. Bind application authorization to employer, role URL, resume hash, and confirmed answers version. Changed materials require renewed version approval.
8. A supported ATS adapter uses the verified official form, local session, approved materials, and confirmed answers.
9. Mark APPLIED only with verified success evidence. Ambiguous submission becomes OUTCOME_UNKNOWN; never blindly retry.

## Preferences

- NYC and commutable metro, full-time, hybrid preferred.
- About USD 100,000+ annual base when available; a target, not an automatic hard cutoff.
- Data Analyst, Senior Data Analyst, BI Analyst, Senior BI Analyst, Business Analytics, light Analytics Engineering, Retail/Commercial Analytics, and relevant Data/AI Analytics.
- Prioritize SQL, business understanding, metrics, modeling, dashboards, stakeholder collaboration, ownership, validation, ETL, requirements, UAT, training, and relevant AI workflows when supported by the resume.
- Exclude roles primarily involving heavy production Spark/Databricks, platform architecture, distributed systems, infrastructure, or software engineering.
- Treat Snowflake/dbt/cloud requirements without evidence as gaps. Never invent production use.

## Visa evidence

H-1B transfer compatibility is an independent gate:

- A: explicit role-level H-1B/transfer support.
- B: no role promise, but substantial employer records within two years.
- C: weak, older, or unrelated occupational evidence.
- Unknown: unverified.

Record the correct legal entity, original statement, URL, and date. Historical LCA records do not guarantee a current role. B/C/Unknown require confirmation of change-of-employer/transfer support. Explicit no-sponsorship overrides a strong skill score. State when no A-level jobs are available.

Daily reports should show a top three and up to 8-12 distinct jobs when available, without padding. Include source links, location/mode, salary, posting age, available applicant activity, estimated business/technical split, match, up to three gaps, suggested timing, and 3-5 exclusions where available.

## Architecture

Keep Streamlit and SQLite. Add a persistent queue, worker, and small search/verification/ATS adapters. The scheduler enqueues daily work; UI reruns never start jobs. Avoid unnecessary multi-agent infrastructure.

Task types: discover, verify, analyze, tailor, apply. Task states: QUEUED, RUNNING, WAITING_USER, SUCCEEDED, FAILED, OUTCOME_UNKNOWN. Keep job statuses separate. Proposed tables: search_runs, job_sources, visa_evidence, resume_versions, application_attempts, task_runs, application_profile. Preserve jobs and api_runs.

Enforce request, pagination, time, cost, and retry limits. Track coverage and truncation. Programs enforce source references, budgets, deduplication, approvals, credentials, and state transitions. Models explain and suggest; they do not establish new resume facts. Chat tools are not automatically available to a standalone worker.

## Credentials and application answers

Reuse dedicated local browser sessions. Never put passwords in chat, Git, SQLite, prompts, or logs. Prefer OS credential storage; models must not read raw passwords. Different employers may require different Workday accounts.

Users enter passwords and handle MFA/CAPTCHA. Do not bypass challenges. Review terms, attestations, and permissions as required by the execution environment. Work authorization, sponsorship, salary expectations, availability, relocation, and voluntary demographic answers must be explicitly user-maintained, never inferred from a resume.

Validate one ATS at a time. Unsupported pages go to manual handling. Live submission is not a test method. Retain verified URLs, material hashes, submission times, application numbers, and success evidence; redact sensitive logs.

## Implementation order

1. Validate OpenAI API with a real key; default budgets $1/day and $20/month.
2. Build and validate discovery/verification, daily inbox, and scheduling.
3. Add fact-checked resume version review and confirmed application answers.
4. Complete one authorized ATS workflow before expanding compatibility.

Provider: OpenAI API, gpt-5.4-mini. Ollama remains an optional alternative. The schedule is saved with enabled=false; saved configuration is not a running scheduler.
