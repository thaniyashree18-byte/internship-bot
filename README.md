# AI Internship Automation System

A local Streamlit app for assigning track-based internship projects, generating welcome and orientation emails, scheduling reviews, and recording GitHub-based feedback. The virtual-date demo works without Gemini, GitHub, Gmail, or Google Calendar credentials.

## Quick start

```powershell
cd internship-bot
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Fill in `.env` only for the integrations you want to use. Never commit `.env`, Gmail app passwords, API keys, `credentials.json`, or OAuth tokens. A Gmail app password requires Google 2-Step Verification.

## Data and integrations

- Intern records are stored in `interns.xlsx`; the application creates it on the first save.
- `logs.csv` records app actions and integration outcomes. `outbox/` contains HTML messages produced in dry-run mode.
- Sample addresses use the reserved `example.com` domain and are not deliverable.
- Gemini and GitHub failures fall back to safe templates or review notes; failures are also written to the log.
- GitHub review reads public repository information. Set `GITHUB_TOKEN` to increase the API rate limit. When several repositories exist, the app chooses the best title/description match, or the most recently updated repository.
- If `credentials.json` is present, the app attempts to create a Google Calendar event with a Meet conference link using the service-account Calendar API. Share the target calendar with the service account. If setup or event creation fails, a clearly labeled placeholder Meet URL is used. Without the file, the same placeholder behavior applies.
- Review cadence is weekly for three reviews. The final review marks the intern Completed and sends a completion email.
- Dry run (the default) writes email content to `outbox/` and does not send it. With dry run disabled, the app sends to `TEST_EMAIL` by default. The explicit **Allow delivery to intern addresses** control is required to deliver to actual intern addresses.

## Demo workflow

1. Open **Interns** and click **Generate 100 sample interns**, or add a record/upload an Excel workbook.
2. In **Assign Tasks**, assign tasks for any unassigned interns. A join date, task, first review date, and deadline are added.
3. In **Send Mails**, create welcome emails. In **Reviews**, create a first-review invite if needed.
4. Use **Simulate next day** to trigger orientations on/after the join date. Use **Simulate next week** to trigger due reviews. Repeat until review three completes the lifecycle.
5. Inspect generated messages in `outbox/` and app actions under **Logs**.

All email actions are opt-in from their page. Dry run is enabled by default, and simulated dates are stored in the current Streamlit session.

## Workbook columns

The application maintains: `ID`, `Name`, `Email`, `GitHub_Username`, `Track`, `Task_Title`, `Task_Description`, `Modules`, `Features`, `Tech_Stack`, `Join_Date`, `Review1_Date`, `Review1_Time`, `Meet_Link`, `Status`, `Review_Count`, `Last_Feedback`, `Next_Task`, `End_Date`.
