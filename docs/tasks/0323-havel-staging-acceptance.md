# 0323: Havel (AI): staging acceptance (owner)

Status: todo
Depends on: 0310 to 0322, 0324 to 0331 merged | Base commit: the `main` commit you deploy (write it in step 4)
Executor: **Owner (Josef)**, not Haiku. About 60 minutes and under $0.50 of API use.

## 1. Objective

Decide go or no-go for Havel (AI) from what it does on Render staging with a real key: the automatic eval (plan section 13), the cases only a person can judge, screenshots, and the spend. Production stays off until this brief says go **and** the lawyer has signed off the 0329 drafts.

## 2. Context

What you need:


- Your Anthropic Console login.
- Render access to the service **ubyhost-staging** (https://ubyhost-staging-01gh.onrender.com; manual deploy, mock UbyPort, synthetic data only).
- Your computer with this repository and `App/.venv` (for step 3), a phone, and the computer's browser.
- A notes file for the results table in step 9. Use only staging test data; never type a real guest's details.

## 3. Files

None in the repository. Your notes file and screenshots stay on your computer.

## 4. Steps

1. **Create the key (owner item 2).**
   1. Open https://console.anthropic.com and sign in.
   2. Click **Settings**, then **Limits**. Set a monthly spend limit of **$10**. Click **Save**.
   3. Click **API keys**, then **Create key**. Name it `ubyhost-staging-havel`. Click **Create**.
   4. Copy the key into your password manager. Never paste it into a chat, a commit, an issue or a PR.

2. **Switch Havel on for staging only.**
   1. Open https://dashboard.render.com and click **ubyhost-staging**.
   2. Click **Environment** in the left menu.
   3. Click **Add Environment Variable**. Key `UBYHOST_AI_FEATURES`, value `havel`.
   4. Click **Add Environment Variable** again. Key `UBYHOST_ANTHROPIC_API_KEY`, value: paste the key.
   5. Click **Add Environment Variable** again. Key `UBYHOST_AI_MONTHLY_USD_HAVEL`, value `5`.
   6. Click **Save Changes**. Do not change any other variable.

3. **Run the automatic eval on your computer** (it uses a throwaway database, not staging).
   1. Open a terminal in the repository folder. Run `git checkout main && git pull`.
   2. Run `UBYHOST_ANTHROPIC_API_KEY=<paste the key> App/.venv/bin/python scripts/havel_eval.py` (one line; the key stays in this terminal only).
   3. Wait about 5 minutes. The last lines show `must`, `should`, `cost` and `SHIP RULE: met` or `NOT met`. Copy those four lines into your notes.
   4. Open the replies file it names (usually `/tmp/havel-eval.md`). Read every reply once. Mark any reply that names a button, page, app, price or feature UbyHost does not have: that is an "invented feature" and a no-go on its own.
   5. Close the terminal so the key leaves its history (`history -c` first if you use bash).

4. **Deploy.**
   1. In Render, on **ubyhost-staging**, click **Manual Deploy**, then **Deploy latest commit**.
   2. Wait until the status says **Live**. Write the commit it shows in your notes.
   3. Open https://ubyhost-staging-01gh.onrender.com/healthz. It must say OK.
   4. Sign in to staging the way you normally do.

5. **Computer checks** (browser window at full width). For each, write ok or what went wrong:
   1. Click **Havel (AI)** at the bottom of the menu on the left. The panel opens with five quick-help topics.
   2. Click **Guest link and PIN**, then **Where do I find the link and PIN?** The answer lists the guest-link steps (not the calendar step). Click **Still need help? Ask Havel** under it and send "and for the second property?". Havel answers or asks which property.
   3. Type "Add a stay at <your test property> next Friday to Sunday, 3 people" and press Enter. A card asks you to confirm with those dates and 3 guests. Click **Add stay**. The stay appears under Stays. Delete it afterwards.
   4. Type "Book cleaning at <test property> Monday 10:00–12:00" (with the dash). The card shows Monday's date, 10:00 and 12:00. Click **Cancel**.
   5. Type "Reset the PIN for <test property>". The card warns that the old PIN stops working. Click **Cancel**.
   6. Type "Sync my calendars". Click **Refresh calendars**. The page says the calendars are syncing.
   7. Type "My police report failed with error 4". Havel offers **Send to UbyHost support** with a summary filled in. Add "staging test" in the note and click **Send to support**. The page says "Forwarded to the UbyHost team". Open **/admin/operations**, section Mail: one `havel_support` row (staging may only log it). Send a second one with a different note and **It's urgent, please call me** ticked (0330): the new row's subject starts with `URGENT` and its body shows the phone number.
   8. Click **This didn't help** under any answer. The thanks line appears with the support card. On **/admin/operations**, section **Havel (AI)**, the question is listed.
   9. Press **Ctrl K**, type "how do i zzqx". The only row says "Ask Havel (AI): how do i zzqx". Press Enter. The panel opens with the text typed in. Do not send.
   10. Open **Help**. The **Ask Havel (AI)** button is at the top. Click it; the panel opens.
   11. Type "Thanks!". Havel answers at once. The remaining-messages line does not go down.

6. **Phone checks** (your phone, signed in to staging):
   1. Tap the Havel button in the top bar. The panel fills the screen; the keyboard does not cover the input.
   2. Ask "How do I add a property?". The steps say "tap", not "click".
   3. Repeat checks 5.3 and 5.7 on the phone.
   4. Switch the language to CS (More, then the language buttons). Ask "Jak připojím kalendář z Bookingu?". The answer is Czech and links the property's calendars.
   5. Switch to VI. Ask "Làm sao để thêm chỗ ở?". The answer is Vietnamese.
   6. Take a screenshot of the panel with an answer, of a confirm card and of the support card. Keep them out of the repository; attach them to the PR conversation only if they show no real person's data.

7. **Spend.**
   1. On staging open **/admin/operations**, section **Havel (AI)**. Write the "Spent this month" line in your notes and the counts per kind.
   2. In the Anthropic Console click **Usage**. The day's cost should be close to the eval cost plus the staging line.
   3. Divide the staging spend by the number of messages you sent. Write the cost per message.

8. **Decide.** Use section 7.

9. **Report.** Paste this table, filled in, into the orchestrator chat:

```text
Commit deployed:
Eval: must __/__  should __/__ (__%)  cost $____  SHIP RULE: ____
Invented features found: none / case numbers
Computer 5.1-5.11: ok / failures
Phone 6.1-6.6: ok / failures
Spend this month on staging: $____  messages sent: __  per message: $____
Decision: GO / NO-GO   Reason:
```

   The orchestrator writes `docs/tasks/0323-report.md` from it and the briefs for any failure.

10. **Afterwards.** To switch Havel off on staging: Render, **ubyhost-staging**, **Environment**, delete `UBYHOST_AI_FEATURES`, **Save Changes**, **Manual Deploy**. The key can stay. Production gets the same three variables only after a GO and the lawyer's sign-off; that is a separate owner step.

## 5. Do not touch

Production (Lightsail): no Havel variables there until a GO and the owner's sign-off of the 0329 drafts. Other staging variables. The data of real guests.

## 6. Commands

Only the eval command of step 3.2, on your own computer. Nothing on a server.

## 7. Acceptance

Go only if all of these hold:

- Step 3 says `SHIP RULE: met` and you found no invented feature.
- Every check in steps 5 and 6 is ok, or each failure has a brief number to fix it.
- Cost per message is under $0.01.
- The owner has confirmed the 0329 assumptions A1 to A6 and signed off the drafts (production only; staging may stay on).


## 8. Stop and ask

- The deploy fails or `/healthz` is not OK: redeploy the previous commit (Render, **Events**, the last good deploy, **Rollback**) and tell the orchestrator.
- Havel shows a real guest's data, or a reply contains a link or e-mail address: switch it off (step 10) and tell the orchestrator at once.

## 9. Report

The table of step 9, pasted into the orchestrator chat. The orchestrator writes `docs/tasks/0323-report.md` and sets `Status: done` or opens fix briefs.
