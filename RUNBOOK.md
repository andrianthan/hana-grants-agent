# Hanna Grants Agent — Operations Runbook

*Owner: Marisa Binder (VP Grants) + Monica Argenti (Grants Manager)*
*Technical contact: Andrian Than (athan@hannacenter.org)*
*Last updated: 2026-04-08*

---

## System Overview

The Hanna Grants Agent automatically:
1. **Scrapes 21 grant sources daily** at 6:00 AM PT (federal, state, foundation, county)
2. **Scores new grants with AI** at 9:00 AM PT using a 7-flag evaluation framework
3. **Sends a daily email** at 9:00 AM PT with scored grants above threshold (6.0+)
4. **Sends a weekly digest** every Friday at 8:00 AM PT summarizing the week
5. **Writes to a shared Excel tracker** in SharePoint (pending admin consent) for approval/denial

No manual steps are needed. The system runs fully automatically via AWS EventBridge schedules.

### Daily Schedule

| Time (PT) | What happens |
|-----------|-------------|
| 6:00 AM | Ingestion pipeline scrapes all 21 sources via Step Functions |
| 9:00 AM | Evaluator scores new grants, appends to Excel tracker, sends daily email |
| Friday 8:00 AM | Weekly digest email sent |

---

## Quick Reference

| Task | How |
|------|-----|
| Check if pipeline ran today | See Section 1 |
| Daily/weekly email didn't arrive | See Section 2 |
| Restart a failed pipeline job | See Section 3 |
| 0 new grants in the email | See Section 4 |
| Add a new grant source | See Section 5 |
| Update Hanna's org profile | See Section 6 |
| Update evaluation criteria or weights | See Section 7 |
| Cost is over budget | See Section 8 |
| Something seems wrong with the scores | See Section 9 |
| **Transfer to Hanna's own accounts** | **See Section 10** |

---

## Section 1: Checking If the Pipeline Ran

The pipeline runs automatically every day at 6:00 AM PT (ingestion) and 9:00 AM PT (scoring + email). You do not need to trigger it manually.

**Simplest check:** Did you receive the daily email at ~9:00 AM? If yes, the pipeline ran.

**If no email (see Section 2) or you want to verify:**

1. Log into the [AWS Console](https://us-west-2.console.aws.amazon.com/states/home?region=us-west-2)
2. Navigate to **Step Functions** → **State machines** → `HannaIngestionPipeline`
3. Click **Executions** tab
4. The most recent execution should show today's date with status **Succeeded**

**What the statuses mean:**
- `Succeeded` — Pipeline ran and completed normally
- `Failed` — Pipeline encountered an error. See Section 3
- `Running` — Pipeline is currently in progress (normal if checked before ~6:30 AM PT)

---

## Section 2: Daily/Weekly Email Didn't Arrive

- **Daily email:** Sent every day at 9:00 AM PT
- **Weekly digest:** Sent every Friday at 8:00 AM PT
- **Sender:** athan@hannacenter.org (via amazonses.com until domain verification is complete)

**Step 1: Check your junk/spam folder.** Until domain verification is complete, Outlook may flag the email as external. Click "It's not junk" to train Outlook.

**Step 2: Check if SES sent it.**
1. AWS Console → **Amazon SES** → **Account dashboard**
2. Look for recent send events
3. If "Sends" shows 0 for today, the evaluator Lambda didn't fire

**Step 3: Check EventBridge.**
1. AWS Console → **EventBridge** → **Rules**
2. Check `HannaDailyEvaluation` (daily) or `HannaFridayDigest` (weekly)
3. Verify the rule is **Enabled** and click **Monitoring** to see trigger history

**If nothing else works:** Contact Andrian Than (athan@hannacenter.org).

---

## Section 3: Restarting a Failed Pipeline

**For a failed ingestion (Step Functions):**

1. AWS Console → **Step Functions** → `GrantIngestionPipeline` → **Executions**
2. Click on the failed execution
3. Look at the **Events** tab — the failed step will be highlighted in red
4. Read the error message. Common errors:
   - `Lambda.AWSLambdaException` on a scraper — that website is temporarily down or changed structure. The rest of the pipeline is unaffected (other scrapers still ran). Log it as a known issue and check again tomorrow.
   - `States.TaskFailed` — a Lambda timeout. Retry the execution by clicking **New execution** and resubmitting the same input.
   - Database connection error — RDS may have been temporarily unavailable. Retry.

**To manually restart:**
1. From the failed execution page, click **New execution**
2. Leave the input as-is (or empty `{}`)
3. Click **Start execution**
4. Monitor the new execution in the **Executions** tab

**For a failed evaluation (daily scoring):**

The evaluator runs automatically at 9:00 AM PT. To re-trigger manually:
```
aws lambda invoke \
  --function-name HannaGrantsStack-HannaEvaluatorFnC3684A6F-GnJpoumtwUtb \
  --cli-binary-format raw-in-base64-out \
  --payload '{"run_all_profiles":true,"send_alert":true}' \
  --region us-west-2 \
  /tmp/eval-output.json
```

---

## Section 4: The Digest Is Empty or Has 0 New Grants

This means either the scrapers found nothing new, or all matches scored below the threshold (6/10).

**Why this might happen:**
- All grant sources were already ingested last week (no new postings) — this is normal during quiet periods
- The scoring threshold (6/10) filtered everything — see Section 9 if you think relevant grants are being missed
- A major scraper broke and is returning 0 results — see below

**Check the scraper health alert:** If 0 new grants are ingested over 7 consecutive days, a CloudWatch alarm fires an email to the technical contact. If you haven't received that alarm email, the scrapers are probably running fine — it's genuinely a slow week.

**If you believe a real grant is being missed:**
1. Note the grant name and funder
2. Check if the funder is in our 21 sources (see `scraper_registry.json`)
3. If not, request adding it (see Section 5)
4. If the threshold feels too strict, lower from 6.0 to 5.0 in `org-materials/EVAL-CRITERIA.md`

---

## Section 5: Adding a New Grant Source

Adding a new grant source to the daily pipeline requires editing `scraper_registry.json` and, if it's a website (not an API), building a new Playwright scraper. This requires developer involvement.

**Your role (no technical skills needed):**
1. Identify the grant source: name, URL, whether it has an RSS feed or API
2. Describe the types of grants it lists
3. Note which Hanna program the grants typically target (e.g., Mental Health Hub, Hanna Institute)
4. Email this information to your technical contact

**Template email to technical contact:**
```
Subject: New grant source to add

Source name: [e.g., California Endowment]
URL: [e.g., https://www.calendow.org/grants]
Grant types: [e.g., community health, health equity, BIPOC communities]
Hanna program match: [e.g., Mental Health Hub, Hanna Institute]
Does it have an API or RSS feed? [Yes/No/Unknown]
Priority: [High/Medium/Low]
```

Your technical contact will add the new entry to `scraper_registry.json` and configure the scraper Lambda. No changes to any other files are required.

---

## Section 6: Updating Hanna's Org Profile

The org profile lives in `org-materials/ORG-PROFILE.md`. This file controls what the AI "knows" about Hanna.

**When to update:**
- A new program launches
- An existing program ends or significantly changes
- Staff headcount changes substantially
- A new major funder relationship is established
- Annual strategic priorities shift (update every July at fiscal year start)

**How to update (no technical skills required):**
1. Open `org-materials/ORG-PROFILE.md` in any text editor or GitHub
2. Make your changes to the relevant section (programs, demographics, strategic priorities)
3. Save the file
4. The system will automatically detect the file has changed (via SHA-256 hash) and regenerate the organization-wide HyDE query on the next run

**Important:** If you change a program that affects a specific department's search profile, also update that department's entry in `org-materials/SEARCH-PROFILES.md` (see Section 6b).

### Section 6b: Updating a Department Search Profile

Department search profiles live in `org-materials/SEARCH-PROFILES.md`. Each profile controls how the AI searches for grants for that specific department.

**When to update a profile:**
- A program launches or ends within that department
- The target population changes
- A known funder is added or removed
- A funder rejection makes re-application premature (add a flag note)

**After updating SEARCH-PROFILES.md:** Contact your technical contact to run `generate_hyde.py --profile-id <profile_id> --force` for the updated profile. This regenerates the search embedding for that department. Without this step, the profile changes won't affect search results until the next scheduled annual regeneration.

---

## Section 7: Updating Evaluation Criteria or Score Weights

The scoring framework lives in `org-materials/EVAL-CRITERIA.md`. This file controls how the AI evaluates and scores each grant.

**What you can safely change:**
- Scoring threshold (currently 6/10 — anything below this is filtered from the digest)
- Flag definitions (e.g., what "heavy reporting burden" means for your team)
- Staff time cost thresholds (e.g., max hours per $X award)
- Weight labels (HIGH/MEDIUM) for each flag

**How to update:**
1. Open `org-materials/EVAL-CRITERIA.md` in any text editor
2. Make your changes
3. Save the file — changes take effect on the next evaluation run (no script needed)

**What requires developer involvement:**
- Adding a new flag category (requires updating the Pydantic schema and Evaluator prompt)
- Changing the scoring scale (currently 1–10)

---

## Section 8: Cost Is Over Budget

Target budget is **< $50/month**. A CloudWatch billing alarm fires an email when AWS spending exceeds $45/month.

**If you receive the billing alarm:**

1. AWS Console → **Billing & Cost Management** → **Cost Explorer**
2. Group by **Service** to see which service is driving cost
3. Most likely culprits and fixes:

| Service over budget | Likely cause | Fix |
|---|---|---|
| Amazon RDS | Nothing — t4g.micro is flat ~$14/mo | Normal cost |
| AWS Lambda | Unusually high invocation count | Check Step Functions for runaway executions |
| Amazon Bedrock | Large batch of grants processed | Check grant ingestion counts in CloudWatch |
| OpenRouter (LLM API) | Many grants scored this month | Normal if grant volume is high; each daily run costs ~$0.10-0.30 |

**Estimated monthly costs:**

| Service | Cost |
|---------|------|
| RDS PostgreSQL (t4g.micro) | ~$14 |
| Lambda (scraper + processing + evaluator) | ~$1-2 |
| Bedrock Titan embeddings | ~$0.01 |
| OpenRouter API (GPT-4.1 for scoring) | ~$2-5 |
| S3, Secrets Manager, Step Functions | ~$1 |
| **Total** | **~$18-22** |

**If you can't identify the cause,** contact Andrian Than.

---

## Section 9: Grants Seem Wrong (Irrelevant Results / Missing Good Grants)

The most common issues and their fixes:

**Issue: Getting irrelevant grants in the digest**

1. Is the correct profile active? Check the digest header — it shows which profile was used (e.g., "Mental Health Hub Digest"). If the wrong profile was selected, re-run with the correct one.
2. Is the scoring threshold too low? If grants scoring 6/10 feel irrelevant, raise the threshold to 7/10 in `EVAL-CRITERIA.md`.
3. Is the org profile outdated? Update `ORG-PROFILE.md` with current programs — stale profiles generate stale results.

**Issue: Good grants are not appearing**

1. Check the grant's deadline — expired grants are filtered out automatically.
2. Check the grant's geography — grants restricted to geographies other than CA/Sonoma are filtered out.
3. Is the grant from a source not in the scraper registry? If so, add it (see Section 5).
4. Is the scoring threshold too high? If you're seeing 0 results but expect matches, lower the threshold from 6/10 to 5/10 in `EVAL-CRITERIA.md`.

**Issue: Relationship flag is wrong**

The system cross-references `org-materials/FUNDER-DIRECTORY.md` to determine if Hanna has an existing relationship with a funder. If a funder is missing from that file, the relationship flag will be incorrect. Update `FUNDER-DIRECTORY.md` with the correct relationship status and re-run the evaluation.

---

## Section 10: Account Transfer Requirements

The system currently runs on Andrian's personal AWS account and OpenRouter API key. Before full handoff, these need to transfer to Hanna Center's own accounts.

### Transfer Checklist

| # | Item | Current State | What Hanna Needs | Priority |
|---|------|--------------|-----------------|----------|
| 1 | **AWS Account** | Andrian's account (215675829417) | Hanna Center's own AWS account | HIGH |
| 2 | **OpenRouter API Key** | Andrian's personal key | Hanna's own OpenRouter account OR direct OpenAI API key | HIGH |
| 3 | **SES Domain Verification** | Individual email verified (athan@hannacenter.org) | Domain verification via DNS DKIM records | MEDIUM |
| 4 | **Azure AD Admin Consent** | App registered, awaiting consent | Admin clicks consent URL (see Admin-Consent-Guide.docx) | MEDIUM |
| 5 | **MS Graph Client Secret** | In Secrets Manager on Andrian's AWS | Move to Hanna's Secrets Manager after AWS transfer | MEDIUM |
| 6 | **DNS DKIM Records** | 3 CNAME records pending | Add to hannacenter.org DNS (see Admin-Consent-Guide.docx) | MEDIUM |
| 7 | **GitHub Repository** | Andrian's GitHub | Transfer repo or fork to Hanna's GitHub org | LOW |

### 1. AWS Account Transfer

**Recommended: Migrate to Hanna's own AWS account**

1. Hanna Center creates an AWS account (or uses an existing one)
2. Install AWS CDK and Node.js on a deployment machine
3. Bootstrap CDK: `cdk bootstrap aws://ACCOUNT_ID/us-west-2`
4. Clone the repo and deploy:
   ```bash
   cd infrastructure
   source .venv/bin/activate
   pip install -r requirements.txt
   cdk deploy \
     --parameters AlertEmail=athan@hannacenter.org \
     --parameters OpenRouterApiKey=sk-or-HANNAS-KEY \
     --parameters MsCredentialsSecretArn=ARN_OF_SECRET \
     --parameters MsSiteHost=hannaboyscenter.sharepoint.com \
     --parameters MsSitePath=/sites/HannaCenterHomeSite \
     --parameters MsWorkbookId=8ae32dd0-39e2-4dc0-84b5-54803fce684c \
     --parameters MsWorkbookUrl="EXCEL_URL_HERE"
   ```
5. Run the backfill script to populate historical grants
6. Verify pipeline runs successfully

**Resources created by CDK (all in us-west-2):**
- RDS PostgreSQL instance (t4g.micro) with pgvector
- 3 Lambda functions (scraper Docker, processing Docker, evaluator Docker)
- Step Functions state machine
- S3 bucket
- API Gateway
- EventBridge rules (3 schedules)
- Secrets Manager secret (DB credentials, auto-generated)
- CloudWatch alarms + SNS topic for billing alerts

### 2. OpenRouter / LLM API Key

The system uses OpenRouter to access GPT-4.1 and GPT-4.1-mini for grant extraction and evaluation.

**Option A: Hanna gets their own OpenRouter account**
1. Sign up at openrouter.ai
2. Add a payment method
3. Generate an API key
4. Redeploy with `--parameters OpenRouterApiKey=sk-or-NEW-KEY`

**Option B: Switch to direct OpenAI API**
1. Sign up at platform.openai.com
2. Generate an API key
3. Update CDK stack: change `OPENAI_BASE_URL` from `https://openrouter.ai/api/v1` to `https://api.openai.com/v1`
4. Update model names: remove `openai/` prefix (e.g., `openai/gpt-4.1` → `gpt-4.1`)
5. Redeploy

**Estimated LLM cost:** ~$2-5/month at current volume.

### 3. SES Domain Verification

Currently using individual email verification. For production, add 3 DKIM CNAME records to hannacenter.org DNS:

| Type | Name | Value |
|------|------|-------|
| CNAME | qf4n6zm6bipjif4iafvlf26szc43d4bg._domainkey.hannacenter.org | qf4n6zm6bipjif4iafvlf26szc43d4bg.dkim.amazonses.com |
| CNAME | v5fnyf2gn3h6crjblmejcemjmwcepdtn._domainkey.hannacenter.org | v5fnyf2gn3h6crjblmejcemjmwcepdtn.dkim.amazonses.com |
| CNAME | jsqyfjkcxvjka3twpcdbvdnsenhvjdhx._domainkey.hannacenter.org | jsqyfjkcxvjka3twpcdbvdnsenhvjdhx.dkim.amazonses.com |

**Note:** These records are specific to the current AWS account. If migrating to a new AWS account, new DKIM tokens will need to be generated.

After adding: emails show as `athan@hannacenter.org` instead of `via amazonses.com`, no more junk/external warnings.

### 4. Azure AD Admin Consent

Already registered as "Hanna Grants Agent" in Hanna's Azure AD tenant. IT admin needs to grant consent — see `output/Admin-Consent-Guide.docx` or use one-click URL:

```
https://login.microsoftonline.com/60791775-2126-4012-80bb-e162cc58cd45/adminconsent?client_id=2827d637-680e-42dc-ab2d-fdd9e85a11fd
```

### 5. MS Graph Client Secret

Stored in AWS Secrets Manager as `hanna-ms-graph-credentials`. After AWS account transfer, recreate in the new account:
```bash
aws secretsmanager create-secret \
  --name hanna-ms-graph-credentials \
  --secret-string '{"tenant_id":"...","client_id":"...","client_secret":"..."}' \
  --region us-west-2
```

**The client secret expires in 24 months (April 2028).** Set a calendar reminder to rotate it: Azure Portal → App registrations → Hanna Grants Agent → Certificates & secrets → New client secret → update Secrets Manager.

### CDK Deploy Parameters (Full Reference)

All configuration is passed at deploy time — nothing is hardcoded in the code:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `AlertEmail` | Email for notifications and billing alerts | athan@hannacenter.org |
| `OpenRouterApiKey` | LLM API key (OpenRouter or OpenAI) | sk-or-... |
| `AllowedIps` | IP whitelist for RDS (default: 0.0.0.0/0) | 203.0.113.0/24 |
| `MsCredentialsSecretArn` | Secrets Manager ARN for MS Graph creds | arn:aws:secretsmanager:... |
| `MsSiteHost` | SharePoint site hostname | hannaboyscenter.sharepoint.com |
| `MsSitePath` | SharePoint site path | /sites/HannaCenterHomeSite |
| `MsWorkbookId` | Excel file item ID in SharePoint | 8ae32dd0-39e2-... |
| `MsWorkbookUrl` | Browser URL to Excel file | https://hannaboyscenter.sharepoint.com/... |

---

## Section 11: System Health Checklist (Monthly)

Run this quick check monthly to confirm the system is healthy:

- [ ] Last Step Functions execution: **Succeeded** (check within last 24 hours)
- [ ] Daily email arrived today
- [ ] Weekly digest arrived on Friday
- [ ] CloudWatch billing alarm has not fired (check inbox)
- [ ] RDS storage under 80% (AWS Console → RDS → Storage)
- [ ] FUNDER-DIRECTORY.md reflects current active grants and relationships
- [ ] ORG-PROFILE.md reflects current programs (especially if anything launched or ended)
- [ ] No scraper showing 0 grants for 7+ consecutive days
- [ ] MS Graph client secret not expiring within 3 months

---

## Section 12: Annual Maintenance (Every July — Fiscal Year Start)

Perform these steps at the start of each fiscal year (July 1):

1. **Update ORG-PROFILE.md** — refresh strategic priorities for the new fiscal year
2. **Update SEARCH-PROFILES.md** — update any programs that launched, ended, or changed scope
3. **Update FUNDER-DIRECTORY.md** — add new active grants; move closed grants to "past funders"
4. **Update EVAL-CRITERIA.md** — review staff time cost thresholds and reporting burden calibration with Marisa
5. **Request HyDE regeneration** — email your technical contact to run `generate_hyde.py --profile-id all --force`
6. **Review scraper registry** — are there new grant sources worth adding? Use Section 5 template.
7. **Review digest quality** — did the past year's digests surface grants worth pursuing? Calibrate scoring threshold accordingly.

---

## Architecture Summary

```
EventBridge (daily 6am PT)
    └─→ Step Functions (ingestion pipeline)
         ├─→ 21x Scraper Lambdas (parallel, Docker/Playwright)
         │    └─→ Processing Lambda (dedup, extract, embed)
         │         └─→ RDS PostgreSQL + pgvector
         └─→ Pipeline logger

EventBridge (daily 9am PT)
    └─→ Evaluator Lambda (Docker)
         ├─→ Sync approvals from Excel (MS Graph)
         ├─→ Score grants (GPT-4.1 via OpenRouter)
         ├─→ Append scored grants to Excel (MS Graph)
         └─→ Send daily email (SES)

EventBridge (Friday 8am PT)
    └─→ Evaluator Lambda → Send weekly digest (SES)
```

**Key files:**
- `scraper_registry.json` — 21 grant sources with URLs, priority, profiles
- `org-materials/ORG-PROFILE.md` — Hanna's organizational profile
- `org-materials/SEARCH-PROFILES.md` — 6 department search profiles
- `org-materials/EVAL-CRITERIA.md` — 7-flag scoring framework
- `infrastructure/stacks/hanna_stack.py` — entire AWS infrastructure as code
- `output/funder_leads_report.md` — 356 foundation leads from 990-PF analysis

---

*This runbook should be reviewed and updated annually or whenever the system changes significantly.*
