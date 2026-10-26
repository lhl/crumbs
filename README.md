# Meta Global AI Developer Hackathon — Participant Guide

Source: https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details

This guide is the all-in-one resource for the event: schedule, rules, technical resources, problem statements, judging, and prizes.

**Key dates (all times ET)**

| When | What |
|---|---|
| Mon, Oct 26, 12:00 PM | Kickoff |
| Oct 27 – Nov 4 | Building period |
| Wed, Nov 4, 9:00 PM | **Submissions due** (also deadline to claim Meta API credits) |
| Nov 5 – Nov 8 | Judging period |
| Mon, Nov 9, 12:00 PM | Closing ceremony, winners announced |
| Mon, Nov 16 | Community vote winner announced |

**Our credits status**

| Provider | Status | Notes |
|---|---|---|
| Meta Model API | ✅ $150 claimed | https://dev.meta.ai/platform |
| Baseten | ⏳ not yet requested | $100 + 2M TPM, first 2,000 participants |
| Modal | ⏳ not yet requested | $100, first 1,000 participants |
| Fireworks | ⏳ not yet requested | $25, selected teams only |

---

## 1. Problem Statements

Your project must build towards one of the following:

- **Build for Your World** — Bring Meta's models into your domain. Solve a problem you know firsthand, free up time and mental space, and make something possible that wasn't before.
- **Push the Frontier** — Use Meta's models to tackle challenges in software, robotics, manufacturing, energy, materials and beyond. Give a machine a new capability, accelerate a scientific experiment, or unlock a better way to understand and control a physical system. Show what becomes possible when these models meet the real world.

**Your project must incorporate Meta's models:**

- Via **[Meta Model API](https://dev.meta.ai/products/meta-model-api)**: [Muse Spark series](https://dev.meta.ai/models/muse-spark), [Muse Wonder](https://dev.meta.ai/models/muse-wonder), [Muse Image](https://dev.meta.ai/models/muse-image), [Muse Voice Transcribe](https://dev.meta.ai/models/muse-voice-transcribe), [SAM 3.1](https://dev.meta.ai/models/sam-3-1)
- **Open weights** (self-run): [Muse Glimmer](https://dev.meta.ai/models/muse-glimmer), [Muse Spark Open](https://dev.meta.ai/models/muse-spark-open)
- **Coding agent**: [Muse Code](https://dev.meta.ai/lp/muse-code)

## 2. Community (Discord)

Join the Hackathon Discord (via Cerebral Valley) to meet participants, get official updates, and form teams.

Getting started:
- Introduce yourself in `#intros` (who you are, skills, what you want to build).
- Optionally find a team in `#team-search` (max team size: 4).

Key channels:
- `#general` — socialize
- `#announcements` — official updates from the CV team
- `#intros` — introductions
- `#team-search` — find teammates
- `#questions` — general questions to Cerebral Valley
- `#office-hours` — questions for the Meta team

## 3. Schedule (all times ET)

All sessions are livestreamed on the Cerebral Valley event livestream page.

### Kickoff
- **Mon, Oct 26 | 12:00 PM** — Opening remarks, hackathon overview, rules, prizes, judging, Meta speaker kickoff.

### Building & Live Sessions
- **Tue, Oct 27 | 12:00–1:00 PM** — *Agents 101: Build a Multimodal AI Agent* (Suraj Subramanian)
- **Wed, Oct 28 | 12:00–1:00 PM** — *Agents 102: Best Practices for Verifiable Agents* (Yash Khare)
- **Fri, Oct 30 | 12:00–1:00 PM** — *Building Specialized Intelligence on Fireworks: From Inference to Training with Muse Open Models* (Sinan Ozdemir)
- **Weekdays during building period, 10–11 AM** — Text-only office hours in Discord `#office-hours` with Meta team members (no livestream).

### Submission Deadline
- **Tue, Nov 3** — Last full day for submission questions and technical troubleshooting.
- **Wed, Nov 4 | 9:00 PM** — Final office hours in Discord; **submissions due via the CV platform**.

### Judging & Closing
- **Thu, Nov 5 – Sun, Nov 8** — Judging period
- **Mon, Nov 9 | 12:00 PM** — Closing ceremony: top 10 teams announced (5 per track), live final-round judging, winners revealed, community vote opens.
- **Mon, Nov 16** — Community vote winner announced on Discord.

**Building period: Oct 27 – Nov 4**

## 4. Rules

- **Open source** — Repositories must be public.
- **Team size** — Max 4 participants. Solo allowed.
- **Demo requirements** — Demo must only highlight features, code, and functionality built during the Hackathon. Judges must be able to clearly identify what was created during the Hackathon; failure to do so can result in immediate disqualification (at judges' sole discretion).
- **New work only** — Work presented must be built during the event. Startups may build on existing products/codebases but must clearly identify what was newly developed.
- **Banned projects** — Disqualified if they violate legal, ethical, or platform policies, or use code, data, or assets you don't have rights to.

### Anti-Projects (avoid)

Generic or policy-violating ideas (not exhaustive):
- Anything using AI to generate/give medical advice (e.g., AI mental health advisor, skin blemish detector)
- Basic RAG applications
- Simple image analyzers
- Simple "AI for Education" chatbots
- AI job application screener
- AI nutrition coach
- Personality analyzers
- Sports analyzers or coaches
- Anything political or involving war

## 5. Meta-Provided Resources

### $150 Meta Model API credits

Every accepted participant gets $150 in Meta Model API credits.

1. Apply via the form: *Meta Global AI Hackathon: Model API Credit Claims* (Google Docs form).
2. Credits are distributed in batches — check the **Billing** page to confirm they're applied.
3. A credit card must be on the account to make API calls. A temporary pre-authorization charge will appear and be released within a few business days.
4. Optionally set a **Spend Limit** notification on the Billing page to avoid spending beyond $150.

**Claim by Wed Nov 4, 9:00 PM ET.** Each participant (solo, team member, or startup entrant) must claim individually — no claiming on someone else's behalf.

### Helpful resources
- **Docs**: Overview · Quickstart guide · Model list
- **Cookbook**: API cookbook · API fundamentals · Muse Code recipes · OSS model cookbook
- **On-demand sessions**:
  - The multimodal intelligence of Muse Spark
  - Building with Muse Spark and Muse Code: from capabilities to production
  - The road ahead: the superintelligence blueprint and what's next

## 6. Inference Partner Resources

> Disclaimer: Credits are not guaranteed and are distributed at the sole discretion of each partner.

### Baseten
- Quickstart: make your first API call in minutes
- Chat Completions API: Python, JavaScript, cURL examples
- Reasoning: understand/read Muse Spark Open's reasoning output
- Vision and Audio: send images and audio to Muse Spark Open
- **Request $100 credits + 2M TPM rate limit** — up to 2,000 participants; reviewed by use case; per individual, not per team.

> ⚠️ Docs use `meta-models/muse-spark-open`. For the hackathon, use **`meta-models/muse-spark-open-1026`** instead.

Help: Baseten channel in the Hackathon Discord.

### Modal
- Introduction to Modal: AI infrastructure platform
- **Request $100 credits** — first 1,000 participants; for running Meta's open-weight models via Endpoints, plus serverless GPUs, sandboxes, and LLM training tools.

Help: Modal documentation.

### Fireworks
- **Request $25 credits for your team** — shortlist of select teams reviewed with Fireworks; selected teams get redemption details by email.

## 7. Submission Process

- Submit via the Cerebral Valley platform by **Nov 4, 9:00 PM ET**. Late submissions not considered.
- One submission per team/startup (not per person).
- Each team appoints a **Representative** to act on behalf of the team/startup and enter the submission.
- Double-check: repo is **public**, video link is **accessible**, and **all contributors are listed** on the submission page.
- **Required: 3-minute demo video** highlighting the specific features, code, and functionality built during the Hackathon. This is one of the primary artifacts judges use, along with code and the live product.

## 8. Judging

**Stage One (pass/fail)** — Does the project reasonably fit the theme and reasonably use the Meta Model API and/or Meta's open-weight models, built during the Hackathon?

**Stage Two (0–10 per criterion):**

| Category | Weight | Description |
|---|---|---|
| Impact | 30% | Real-world potential? Who benefits and how much? Could people actually use it? Fits a problem statement? |
| Use of Meta AI Tooling | 25% | How creatively were Meta's tools used? Beyond a basic integration? Surfaced surprising capabilities? |
| Technical Depth & Execution | 20% | Sound, thoughtfully refined engineering? Real craft? |
| Demo | 25% | Working, impressive demo? Holds up live? Is the video genuinely cool to watch? |

**Stage Three** — Top 5 per track go to a final round; final judges watch the video demos live and rank them using the same rubric.

## 9. Prizes

**Total prize pool: $1,000,000** across 2 tracks + bonus prizes.

### Track: Indie Developer ($400,000)

| Place | Prize |
|---|---|
| 1st | $150K |
| 2nd | $100K |
| 3rd | $75K |
| 4th | $50K |
| 5th | $25K |

### Track: Startups ($550,000)

| Place | Prize |
|---|---|
| 1st | $250K |
| 2nd | $150K |
| 3rd | $75K |
| 4th | $50K |
| 5th | $25K |

### Bonus Prizes from Meta ($50,000)

| Prize | Amount | What it rewards | How it is judged |
|---|---|---|---|
| Most Viral Project | $20,000 | Highest engagement on X after the event | Post your demo on X and submit the post link via the platform. Total engagement (likes, reposts, comments) through Nov 8 EOD. |
| Best Build on Meta Open Weight Models | $10,000 | Best project using Muse Glimmer or Muse Spark Open, on your own hardware or partner inference | Flagged in first judging round; infra partner verifies it runs on an eligible Meta open-weight model. |
| Community Vote | $10,000 | Most votes in the public gallery | One vote per verified account; announced Nov 16. |
| Best Agentic Use-Case | $5,000 | Strongest use of AI agents for meaningful tasks, decisions, or multi-step workflows | Judged on autonomy, effectiveness, and practical usefulness. |
| Best Creative Build | $5,000 | Most original creative project using Muse Image or Muse Wonder | Flagged in first round; judged on originality, execution, and effective model use. |
