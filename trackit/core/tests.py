"""Core application tests"""
import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import Filter, TicketSnapshot, TicketUpdate, EmailToken
from utils.token_service import TokenService


@pytest.mark.models
class FilterModelTest(TestCase):
    """Test Filter model"""
    
    def setUp(self):
        self.filter = Filter.objects.create(
            name='Test Filter',
            jira_filter_id='12345',
            snapshot_time='19:00:00',
            report_time='21:00:00',
            admin_email='admin@test.com'
        )
    
    def test_filter_creation(self):
        """Test filter is created correctly"""
        assert self.filter.id is not None
        assert self.filter.name == 'Test Filter'
        assert self.filter.active is True
    
    def test_filter_string_representation(self):
        """Test filter string representation"""
        assert str(self.filter) == 'Test Filter'


@pytest.mark.models
class TicketSnapshotTest(TestCase):
    """Test TicketSnapshot model"""
    
    def setUp(self):
        self.filter = Filter.objects.create(
            name='Test Filter',
            jira_filter_id='12345',
            snapshot_time='19:00:00',
            report_time='21:00:00',
            admin_email='admin@test.com'
        )
        
        self.snapshot = TicketSnapshot.objects.create(
            filter=self.filter,
            ticket_id='BUG-101',
            title='Test Bug',
            assignee='John Doe',
            status='In Progress',
            priority='High',
            updated=timezone.now(),
            snapshot_date=timezone.now().date(),
            snapshot_json={'test': 'data'}
        )
    
    def test_snapshot_creation(self):
        """Test snapshot is created correctly"""
        assert self.snapshot.ticket_id == 'BUG-101'
        assert self.snapshot.filter == self.filter
    
    def test_snapshot_query(self):
        """Test querying snapshots"""
        snapshots = TicketSnapshot.objects.filter(ticket_id='BUG-101')
        assert snapshots.count() == 1


@pytest.mark.models
class EmailTokenTest(TestCase):
    """Test EmailToken model"""
    
    def setUp(self):
        self.filter = Filter.objects.create(
            name='Test Filter',
            jira_filter_id='12345',
            snapshot_time='19:00:00',
            report_time='21:00:00',
            admin_email='admin@test.com'
        )
        
        self.token = EmailToken.objects.create(
            assignee_email='user@test.com',
            token='test-token',
            filter=self.filter,
            expires_at=timezone.now() + timedelta(hours=2),
        )
    
    def test_token_creation(self):
        """Test token is created correctly"""
        assert self.token.token == 'test-token'
        assert not self.token.used
    
    def test_token_validity(self):
        """Test token validity check"""
        assert self.token.is_valid()
    
    def test_token_expiry(self):
        """Test expired token detection"""
        self.token.expires_at = timezone.now() - timedelta(hours=1)
        self.token.save()
        assert not self.token.is_valid()
    
    def test_mark_token_used(self):
        """Test marking token as used"""
        self.token.mark_used('127.0.0.1')
        assert self.token.used
        assert self.token.ip_address == '127.0.0.1'


@pytest.mark.unit
class TokenServiceTest(TestCase):
    """Test TokenService"""
    
    def test_generate_token(self):
        """Test token generation"""
        token = TokenService.generate_token(1, 'test@example.com')
        assert token is not None
        assert isinstance(token, str)
    
    def test_validate_token(self):
        """Test token validation"""
        token = TokenService.generate_token(1, 'test@example.com')
        payload = TokenService.validate_token(token)
        assert payload['filter_id'] == 1
        assert payload['assignee_email'] == 'test@example.com'
    
    def test_invalid_token(self):
        """Test invalid token raises exception"""
        with pytest.raises(Exception):
            TokenService.validate_token('invalid-token')


@pytest.mark.views
@pytest.mark.django_db
class UpdatePageViewTest:
    """Test UpdatePageView"""
    
    def test_update_page_with_valid_token(self, client):
        """Test accessing update page with valid token"""
        # This would require setting up test data and mocking JWT
        pass
    
    def test_update_page_with_expired_token(self, client):
        """Test accessing update page with expired token"""
        # This would require mocking JWT expiry
        pass


@pytest.mark.api
@pytest.mark.django_db
class FilterAPITest:
    """Test Filter API endpoints"""
    
    def test_list_filters(self, client):
        """Test listing filters"""
        # Create test data
        Filter.objects.create(
            name='Test Filter',
            jira_filter_id='12345',
            snapshot_time='19:00:00',
            report_time='21:00:00',
            admin_email='admin@test.com'
        )
        
        # This would require authentication setup
        # response = client.get('/api/v1/filters/')
        # assert response.status_code == 200


# Example of running specific test
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
