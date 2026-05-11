# TrackIt (Smart Jira Accountability Automation System) (Python Django/FastApi)

## Objective

Automate daily ticket follow-up, assignee accountability, progress collection, and management reporting for multiple Jira filters without requiring manual calls.

---

# Problem Statement

Currently:

- Manager/Admin manually opens Jira filters
- Collects bugs/tasks
- Calls assignees individually
- Collects updates
- Tracks commitments manually
- Shares summary manually over email/Teams

Problems:

- Time consuming
- No consistency
- No historical accountability
- Difficult to identify non-performers
- Difficult to compare daily movement

---

# Solution Overview

Build an automated system that:

1. Admin configures Jira filters. (Beautiful page)
2. System automatically takes daily ticket snapshots.
3. System groups tickets by assignee.
4. Sends assignees a consolidated email.
5. Provides secure expirable update link.
6. Assignees update all tickets from one page. (Beautiful page)
7. System compares snapshots.
8. Generates analytics and beautiful markdown reports.
9. Sends final report to admin.

---

# User Roles

## 1. Admin

Can:

- Add Jira filters
- Configure schedule
- Receive daily reports
- View history
- View analytics

---

## 2. Assignee (No need to create entry in DB)

Can:

- Receive daily reminder
- Open secure update page
- Submit updates for all assigned tickets

---

# Functional Requirements

---

# FR-1 Filter Management

## Admin can:

### Add Filter

Fields:

```json
{
  "filter_name": "Backend Bugs",
  "jira_filter_id": "12345",
  "snapshot_time": "19:00",
  "report_time": "21:00",
  "admin_email": "admin@company.com"
}
```

### Actions:

- Create
- Edit
- Disable
- Delete

---

# FR-2 Snapshot Engine

At configured snapshot time:

Example:

7:00 PM

System:

- Calls Jira API
- Fetches tickets

JQL:

```sql
filter=12345
```

Extract:

```json
{
  "ticket_id": "BUG-101",
  "title": "Login issue",
  "status": "In Progress",
  "assignee": "John",
  "priority": "High",
  "updated": "timestamp"
}
```

Store snapshot.

---

# FR-3 Assignee Grouping

System groups tickets by assignee.

Example:

```json
{
  "John": [
    "BUG-101",
    "BUG-102"
  ],
  "Alice": [
    "BUG-103"
  ]
}
```

---

# FR-4 Reminder Email

Send consolidated email to assignee.

Example:

Subject:

```txt
Daily Ticket Update Required
```

Body:

```txt
Hi John,

You have 5 assigned tickets.

Please update before 9 PM.

Tickets:
- BUG-101
- BUG-102
- BUG-103

Update Link:
https://tracker.company.com/update/token
```

---

# FR-5 Secure Update Link

Link must:

- Be unique
- Be tokenized
- Be expirable

Validity:

```txt
2 hours
```

Example:

```txt
JWT + DB validation
```

---

# FR-6 Update Page (SSR)

Technology:

- Django Templates
or
- Next.js SSR

Page shows:

---

## Assignee Details

```txt
John Doe
5 Tickets
```

---

## Ticket Cards

For each ticket:

```txt
---------------------------------
BUG-101
Fix login issue

[ Status ]

[ Completion ETA ]

[ Update Notes ]

[ Blockers ]

---------------------------------
```

Fields:

### ETA

```txt
Tomorrow EOD
```

### Update

```txt
Fixed backend logic.
Testing pending.
```

### Submit

```txt
Save
```

---

# FR-7 Snapshot Comparison

At 9 PM:

System fetches filter again.

Compare:

## New Tickets

Detect:

```txt
Present now but absent in snapshot.
```

---

## Removed Tickets

Detect:

```txt
Present in snapshot but absent now.
```

---

## Status Changes

Example:

```txt
BUG-101

Yesterday:
In Progress

Today:
Done
```

---

# FR-8 Daily Analytics (Use OpenAi Api if Needed)

Compute:

---

## Assignee Metrics

### Ticket Count

```txt
Who owns most tickets?
```

---

### Update Compliance

```txt
Who submitted updates?
Who skipped?
```

---

### Ticket Movement

```txt
Resolved
Moved
Blocked
```

---

### New Tickets

```txt
Added after snapshot
```

---

### Carry Forward

```txt
Pending since yesterday
```

---

# FR-9 Markdown Report Generation

Generate beautiful markdown.

---

## Example

```md
# Daily Jira Report
Date: 2026-05-08

---

# Filter
Backend Bugs

---

# Summary

| Metric | Count |
|--------|------|
| Total Tickets | 52 |
| Updated | 45 |
| Missed | 7 |
| New Tickets | 3 |
| Resolved | 8 |

---

# Top Load

| Assignee | Tickets |
|----------|---------|
| John | 12 |
| Alice | 10 |
| Mike | 8 |

---

# No Update Submitted

🚨

| Assignee | Ticket Count |
|----------|-------------|
| Mike | 8 |
| Bob | 4 |

---

# New Tickets

| Ticket |
|--------|
| BUG-501 |
| BUG-502 |

---

# Status Movement

| Ticket | Yesterday | Today |
|--------|----------|------|
| BUG-101 | In Progress | Done |
| BUG-205 | Open | Testing |

---

# Resolved Today

🏆

- John → 4
- Alice → 3

---

# Carry Forward

| Ticket | Assignee |
|--------|----------|
| BUG-301 | Mike |
| BUG-302 | Bob |

---
```

---

# FR-10 Admin Delivery

Send report to admin via:

- Email
- Teams (optional)
- Slack (optional)

Attachment:

```txt
report.md
```


---

# Database Design

---

## filters

```sql
id
name
jira_filter_id
snapshot_time
report_time
admin_email
active
```

---

## ticket_snapshots

```sql
id
filter_id
ticket_id
assignee
status
snapshot_date
snapshot_json
```

---

## ticket_updates

```sql
id
ticket_id
assignee
eta
update_note
blockers
submitted_at
```

---

## email_tokens

```sql
id
user_id
token
expires_at
used
```

---

# Scheduler Jobs

---

## 7 PM

```txt
snapshot_job
```

Tasks:

- Fetch Jira
- Save snapshot
- Group tickets
- Send emails

---

## 9 PM

```txt
report_job
```

Tasks:

- Fetch Jira
- Compare snapshots
- Generate analytics
- Generate markdown
- Send report

---

# Non Functional Requirements

---

## Performance

Support:

```txt
100 filters
5000 tickets
```

---

## Security

- Tokenized links
- Expiry
- Single-use tokens

---

## Reliability

Retry:

- Jira API
- Email

---

## Auditability

Track:

- Who opened link
- Who submitted updates
- Submission time

---

# Future Enhancements

- Teams adaptive cards
- AI summary
- Commitment score
- Reliability score
- Trend charts
- Monthly leaderboard

---