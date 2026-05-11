# TrackIt Quick Reference Guide

## 🚀 Get Started in 5 Minutes

### Docker (Recommended)

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your Jira/email credentials

# 2. Start everything
docker-compose up -d

# 3. Initialize database
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser

# 4. Access
# Web: http://localhost:8000
# Admin: http://localhost:8000/admin/
# API: http://localhost:8000/api/v1/
```

### Local Development

```bash
# 1. Setup
./quickstart.sh  # Linux/macOS
# or
quickstart.bat   # Windows

# 2. Start services
redis-server     # Terminal 1
celery -A config worker -l info     # Terminal 2
celery -A config beat -l info       # Terminal 3
python manage.py runserver          # Terminal 4

# 3. Visit http://localhost:8000
```

---

## 📋 Common Tasks

### Create Jira Filter

1. Go to admin dashboard: `/dashboard/`
2. Click "Create New Filter"
3. Enter:
   - **Filter Name:** Display name
   - **Jira Filter ID:** From Jira URL (e.g., 12345)
   - **Snapshot Time:** Daily snapshot time (19:00)
   - **Report Time:** Daily report time (21:00)
   - **Admin Email:** Where to send reports

### View Daily Report

1. Go to `/dashboard/`
2. Click filter name
3. Click "Latest Report"
4. View or download markdown

### Check API

```bash
# List filters
curl http://localhost:8000/api/v1/filters/

# Create filter (requires token)
curl -X POST http://localhost:8000/api/v1/filters/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -d '{
    "name": "My Filter",
    "jira_filter_id": "123",
    "snapshot_time": "19:00",
    "report_time": "21:00",
    "admin_email": "admin@example.com"
  }'
```

---

## 🔧 Configuration

### Environment Variables

```env
# Required
JIRA_BASE_URL=https://jira.company.com
JIRA_USERNAME=bot@company.com
JIRA_API_TOKEN=your-token-here

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL=noreply@trackit.local

# Database (Docker uses defaults)
DB_NAME=trackit
DB_USER=postgres
DB_PASSWORD=postgres

# Django
SECRET_KEY=your-secret-key
DEBUG=False  # Set to False in production
```

### Schedule Configuration

Snapshots and reports run based on times you set in the admin interface. Times are in UTC.

---

## 📊 Workflow

```
7:00 PM (Snapshot Time)
↓
[snapshot_job runs]
↓
- Fetch tickets from Jira
- Create snapshot
- Group by assignee
- Send emails with update links
↓
Assignees receive email

Assignees click link and submit updates
↓
9:00 PM (Report Time)
↓
[report_job runs]
↓
- Compare snapshots
- Compute analytics
- Generate markdown
- Send report to admin
↓
Admin receives email with report
```

---

## 🎯 Key Files

| File | Purpose |
|------|---------|
| `trackit/core/models.py` | Database models |
| `trackit/api/views.py` | REST API endpoints |
| `trackit/scheduler/tasks.py` | Scheduled jobs |
| `trackit/utils/jira_service.py` | Jira integration |
| `trackit/utils/email_service.py` | Email sending |
| `trackit/templates/update_page.html` | Update form UI |
| `.env` | Configuration |
| `docker-compose.yml` | Container setup |

---

## 🐛 Troubleshooting

### Jobs not running

```bash
# Check Celery worker
docker-compose logs celery-worker

# Check Celery beat
docker-compose logs celery-beat

# Check Redis
docker-compose exec redis redis-cli ping
```

### Database connection error

```bash
# Check PostgreSQL
docker-compose exec postgres psql -U postgres -d trackit -c "SELECT 1"

# Reset database
docker-compose down -v
docker-compose up -d
docker-compose exec web python manage.py migrate
```

### Email not sending

```bash
# Check email config in .env
# Test sending:
cd trackit
python manage.py shell

from django.core.mail import send_mail
send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

---

## 📱 API Examples

### Authenticate

```bash
# Get API token
curl -X POST http://localhost:8000/api-auth/token/ \
  -d "username=admin&password=password"

# Use token
curl http://localhost:8000/api/v1/filters/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### Create Filter

```bash
curl -X POST http://localhost:8000/api/v1/filters/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Backend Bugs",
    "jira_filter_id": "12345",
    "snapshot_time": "19:00",
    "report_time": "21:00",
    "admin_email": "admin@example.com"
  }'
```

### Get Reports

```bash
curl http://localhost:8000/api/v1/reports/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### Submit Updates

```bash
curl -X POST http://localhost:8000/api/v1/updates/submit_updates/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "jwt_token_from_email",
    "updates": [
      {
        "ticket_id": "BUG-101",
        "eta": "Tomorrow EOD",
        "update_note": "Fixed the issue",
        "blockers": ""
      }
    ]
  }'
```

---

## 📚 Documentation

- **README.md** - Full overview
- **DEPLOYMENT.md** - Production setup
- **IMPLEMENTATION_SUMMARY.md** - What was built
- **CONTRIBUTING.md** - How to contribute
- **plan.md** - Original requirements

---

## 🚦 Health Checks

```bash
# Basic health
curl http://localhost:8000/health/
# Response: {"status": "healthy", "service": "TrackIt"}

# Detailed health
curl http://localhost:8000/health/detailed/
# Response: {
#   "status": "healthy",
#   "database": {"status": "healthy"},
#   "redis": {"status": "healthy"},
#   "cache": {"status": "healthy"}
# }
```

---

## 💾 Backup & Restore

```bash
# Backup database
docker-compose exec postgres \
  pg_dump -U postgres trackit > backup.sql

# Restore database
docker-compose exec -T postgres \
  psql -U postgres trackit < backup.sql

# Backup volumes
docker run --rm \
  -v trackit_postgres_data:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/postgres_backup.tar.gz -C /data .
```

---

## 🔄 Restart Services

```bash
# Restart web
docker-compose restart web

# Restart worker
docker-compose restart celery-worker

# Restart beat
docker-compose restart celery-beat

# Full restart
docker-compose down
docker-compose up -d
```

---

## 📈 Monitoring

```bash
# View logs
docker-compose logs -f                    # All services
docker-compose logs -f web               # Just web
docker-compose logs -f celery-worker     # Just worker

# Check running processes
docker-compose ps

# Access database
docker-compose exec postgres psql -U postgres -d trackit

# Access Redis
docker-compose exec redis redis-cli
```

---

## 🔐 Security Checklist

- [ ] Change SECRET_KEY in .env
- [ ] Set strong database password
- [ ] Configure email credentials securely
- [ ] Add Jira API token
- [ ] Use HTTPS in production
- [ ] Configure firewall rules
- [ ] Regular security updates
- [ ] Monitor access logs
- [ ] Backup database regularly
- [ ] Review user permissions

---

## 📞 Support

- **Issues:** Open on GitHub
- **Docs:** See README.md
- **Deployment:** See DEPLOYMENT.md
- **Contributing:** See CONTRIBUTING.md

---

## ✨ Tips & Tricks

### Speed up snapshot times
Reduce snapshot size by filtering in Jira JQL

### Improve report clarity
Add custom CSS in templates/base.html

### Monitor task queue
```bash
docker-compose exec celery-worker \
  celery -A config inspect active
```

### Debug tasks
Set `CELERY_TASK_ALWAYS_EAGER = True` in dev to run tasks synchronously

### Custom email template
Edit templates/emails/reminder.html

---

**Happy tracking! 🎉**
