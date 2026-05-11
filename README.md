# TrackIt - Smart Jira Accountability Automation System

A fully automated system that streamlines Jira ticket follow-up, tracks assignee accountability, collects daily progress updates, and generates management reports without manual intervention.

## 🎯 Features

- **Automated Jira Filter Snapshots**: Daily snapshots of Jira filters at configured times
- **Smart Ticket Grouping**: Automatic grouping of tickets by assignee
- **Secure Update Links**: Tokenized, expiring email links for secure ticket updates
- **Beautiful Update Page**: Elegant interface for assignees to submit all updates in one place
- **Snapshot Comparison**: Automatic detection of new, removed, and status-changed tickets
- **Analytics Engine**: Comprehensive metrics including compliance rates, top loads, and trends
- **Markdown Reports**: Beautiful, professional daily reports sent to admins
- **Task Scheduling**: Automated jobs using Celery Beat for consistent timing
- **Email Integration**: HTML and plain-text email templates
- **Admin Dashboard**: Intuitive interface for filter management and report viewing
- **Fully Dockerized**: Complete Docker setup with compose for easy deployment

## 📋 Requirements

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (for containerized deployment)

## 🚀 Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/trackit.git
   cd trackit
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Setup database**
   ```bash
   cd trackit
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Collect static files**
   ```bash
   python manage.py collectstatic
   ```

7. **Start Redis** (separate terminal)
   ```bash
   redis-server
   ```

8. **Start Celery Worker** (separate terminal)
   ```bash
   cd trackit
   celery -A config worker --loglevel=info
   ```

9. **Start Celery Beat** (separate terminal)
   ```bash
   cd trackit
   celery -A config beat --loglevel=info
   ```

10. **Start Django development server**
    ```bash
    cd trackit
    python manage.py runserver
    ```

Visit `http://localhost:8000` and login to the admin dashboard.

### Docker Deployment

1. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Build and start services**
   ```bash
   docker-compose up -d
   ```

3. **Initialize database**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

4. **Access the application**
   - Web: `http://localhost:8000`
   - API: `http://localhost:8000/api/v1/`
   - Admin: `http://localhost:8000/admin/`

## 📁 Project Structure

```
trackit/
├── core/                    # Core app with models and views
│   ├── models.py           # Database models
│   ├── views.py            # Template views
│   ├── urls.py             # URL routing
│   └── admin.py            # Admin configuration
├── api/                     # REST API app
│   ├── serializers.py      # DRF serializers
│   ├── views.py            # API views
│   └── urls.py             # API routes
├── scheduler/              # Celery tasks
│   └── tasks.py            # Scheduled jobs
├── utils/                  # Utility services
│   ├── jira_service.py     # Jira API integration
│   ├── email_service.py    # Email handling
│   ├── token_service.py    # Token generation
│   ├── snapshot_service.py # Snapshot logic
│   └── analytics_service.py # Report generation
├── templates/              # Django HTML templates
├── static/                 # CSS, JavaScript, images
└── config/                 # Project settings
    ├── settings.py         # Django settings
    ├── urls.py            # Main URL config
    ├── wsgi.py            # WSGI application
    └── celery.py          # Celery configuration
```

## 🔧 Configuration

### Key Environment Variables

```env
# Django
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=trackit.example.com

# Database
DB_NAME=trackit
DB_USER=postgres
DB_PASSWORD=secure-password
DB_HOST=postgres

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL=noreply@trackit.example.com

# Jira
JIRA_BASE_URL=https://jira.company.com
JIRA_USERNAME=bot@company.com
JIRA_API_TOKEN=your-jira-api-token

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

## 📊 API Endpoints

### Filters
- `GET /api/v1/filters/` - List all filters
- `POST /api/v1/filters/` - Create new filter
- `GET /api/v1/filters/{id}/` - Get filter details
- `PUT /api/v1/filters/{id}/` - Update filter
- `DELETE /api/v1/filters/{id}/` - Delete filter
- `POST /api/v1/filters/{id}/validate_jira_filter/` - Validate Jira filter

### Updates
- `GET /api/v1/updates/` - List all updates
- `POST /api/v1/updates/submit_updates/` - Submit ticket updates via token

### Reports
- `GET /api/v1/reports/` - List all reports
- `GET /api/v1/reports/{id}/` - Get specific report

## 🔐 Security Features

- **JWT Token Authentication**: Secure tokenized links for email updates (2-hour expiry)
- **CSRF Protection**: Django CSRF tokens on all forms
- **SQL Injection Prevention**: Django ORM with parameterized queries
- **XSS Protection**: Template auto-escaping
- **Rate Limiting**: Configurable rate limiting (implement with django-ratelimit)
- **HTTPS Enforcement**: Automatic redirect in production
- **Secure Cookies**: Secure, HttpOnly, SameSite cookies

## 📈 Workflow

1. **7:00 PM - Snapshot Job**
   - System fetches all tickets from configured Jira filters
   - Groups tickets by assignee
   - Sends reminder emails with secure update links
   - Saves snapshot to database

2. **9:00 PM - Report Job**
   - Fetches current Jira state
   - Compares with earlier snapshot
   - Detects new, removed, and status-changed tickets
   - Computes analytics and metrics
   - Generates beautiful markdown report
   - Sends report to admin email

3. **Assignee Flow**
   - Receives email with unique secure link
   - Clicks link to access update page
   - Submits ETA, status, and blockers for all tickets
   - System records updates and marks link as used

## 🧪 Testing

Run tests with pytest:

```bash
pytest
pytest --cov=trackit  # With coverage
pytest -v             # Verbose output
```

## 📝 Database Models

- **Filter**: Configuration for Jira filters
- **TicketSnapshot**: Point-in-time snapshot of tickets
- **TicketUpdate**: Assignee updates for tickets
- **EmailToken**: Secure, expiring tokens for email links
- **SnapshotComparison**: Comparison results between snapshots
- **DailyAnalytics**: Computed metrics for the day
- **DailyReport**: Generated markdown reports

## 🐳 Docker Images

- `postgres:15-alpine` - PostgreSQL database
- `redis:7-alpine` - Redis cache and message broker
- `nginx:alpine` - Nginx reverse proxy
- `python:3.11-slim` - Custom built Django application

## 📦 Deployment

### Production Checklist

- [ ] Set `DEBUG=False` in .env
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure database with strong password
- [ ] Set up email service (Gmail, SendGrid, etc.)
- [ ] Configure Jira API credentials
- [ ] Setup SSL/TLS certificates
- [ ] Configure domain in `ALLOWED_HOSTS`
- [ ] Setup monitoring and logging
- [ ] Configure backups for PostgreSQL
- [ ] Setup monitoring for Redis
- [ ] Review security settings

### Scaling

- Scale Celery workers: `docker-compose up -d --scale celery-worker=4`
- Use managed database (RDS, Cloud SQL)
- Use managed Redis (ElastiCache, MemoryStore)
- Setup reverse proxy with load balancing
- Use CDN for static files

## 🐛 Troubleshooting

### Database connection issues
```bash
# Check PostgreSQL container
docker-compose logs postgres

# Reset database
docker-compose exec web python manage.py migrate --fake-initial
```

### Celery tasks not running
```bash
# Check Celery worker logs
docker-compose logs celery-worker

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Email not sending
- Check `EMAIL_BACKEND` setting
- Verify SMTP credentials
- Check logs in `logs/trackit.log`

## 📄 License

This project is licensed under the MIT License.

## 👥 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review the plan.md for feature details

---

**Built with ❤️ for team accountability and transparency**
