"""Jira API Integration Service"""
import requests
import logging
import time
from django.conf import settings
from typing import List, Dict, Any
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 1.0):
    """
    Decorator to retry a function with exponential backoff
    
    Args:
        max_retries: Maximum number of retries
        backoff_factor: Base backoff time in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    
                    # Don't retry on 4xx client errors (except 429)
                    if hasattr(e, 'response') and e.response is not None:
                        status_code = e.response.status_code
                        if 400 <= status_code < 500 and status_code != 429:
                            raise
                    
                    # Calculate backoff time with exponential increase
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}. "
                            f"Retrying in {wait_time}s... Error: {str(e)}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}")
            
            raise last_exception
        
        return wrapper
    return decorator



class JiraService:
    """Service to interact with Jira API"""
    
    def __init__(self):
        self.base_url = settings.JIRA_BASE_URL
        self.username = settings.JIRA_USERNAME
        self.api_token = settings.JIRA_API_TOKEN
        self.timeout = 30
    
    def _get_auth(self):
        """Jira Cloud uses Basic Auth (email + API token)"""
        from requests.auth import HTTPBasicAuth
        return HTTPBasicAuth(self.username, self.api_token)
    
    def _get_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    
    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Jira API with automatic retry logic"""
        url = f"{self.base_url}/rest/api/3/{endpoint}"
        headers = self._get_headers()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Jira API request failed: {str(e)}")
            raise
    
    def fetch_filter_tickets(self, filter_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all tickets from a Jira filter using JQL
        
        Args:
            filter_id: Jira filter ID
            
        Returns:
            List of ticket dictionaries
        """
        try:
            jql = f"filter={filter_id}"
            all_issues = []
            start_at = 0
            max_results = 50
            
            while True:
                response = self._make_request(
                    'GET',
                    'search/jql',
                    params={
                        'jql': jql,
                        'fields': 'key,summary,status,assignee,emailAddress,priority,updated',
                        'startAt': start_at,
                        'maxResults': max_results,
                    }
                )
                
                issues = response.get('issues', [])
                if not issues:
                    break
                
                all_issues.extend(issues)
                start_at += max_results
                
                if start_at >= response.get('total', 0):
                    break
            
            # Transform to required format
            tickets = []
            for issue in all_issues:
                ticket = {
                    'ticket_id': issue['key'],
                    'title': issue['fields'].get('summary', ''),
                    'status': issue['fields']['status']['name'],
                    'assignee': issue['fields']['assignee']['emailAddress'] if issue['fields'].get('assignee') else 'Unassigned',
                    'priority': issue['fields']['priority']['name'] if issue['fields'].get('priority') else 'Unknown',
                    'updated': issue['fields']['updated'],
                }
                tickets.append(ticket)
            
            logger.info(f"Fetched {len(tickets)} tickets from filter {filter_id}")
            return tickets
        
        except Exception as e:
            logger.error(f"Failed to fetch filter tickets: {str(e)}")
            raise
    
    def get_filter_details(self, filter_id: str) -> Dict[str, Any]:
        """Get details of a Jira filter"""
        try:
            response = self._make_request('GET', f'filter/{filter_id}')
            return response
        except Exception as e:
            logger.error(f"Failed to get filter details: {str(e)}")
            raise
    
    def validate_filter(self, filter_id: str) -> bool:
        """Check if a filter exists and is accessible"""
        try:
            self.get_filter_details(filter_id)
            return True
        except:
            return False
