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

    _qa_tester_field_id: str = None  # class-level cache — discovered once per process

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
    
    def _get_qa_tester_field_id(self) -> str:
        """Discover the custom field ID for 'QA Tester' from Jira, cached per process."""
        if JiraService._qa_tester_field_id is not None:
            return JiraService._qa_tester_field_id
        try:
            fields = self._make_request('GET', 'field')
            for f in fields:
                if f.get('name', '').strip().lower() == 'qa tester':
                    JiraService._qa_tester_field_id = f['id']
                    logger.info(f"Discovered QA Tester field id: {f['id']}")
                    return f['id']
            logger.warning("QA Tester custom field not found in Jira fields list")
        except Exception as e:
            logger.error(f"Failed to discover QA Tester field: {e}")
        return None

    def fetch_filter_tickets(self, filter_id: str, use_qa_tester: bool = False) -> List[Dict[str, Any]]:
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
            max_results = 100
            next_page_token = None
            # If QA filter: discover and include the QA Tester custom field
            qa_field_id = self._get_qa_tester_field_id() if use_qa_tester else None
            fields_list = ['summary', 'status', 'assignee', 'priority', 'issuetype', 'updated']
            if qa_field_id:
                fields_list.append(qa_field_id)

            while True:
                body = {
                    'jql': jql,
                    'fields': fields_list,
                    'fieldsByKeys': True,
                    'maxResults': max_results,
                }
                if next_page_token:
                    body['nextPageToken'] = next_page_token

                response = self._make_request('POST', 'search/jql', json=body)

                issues = response.get('issues', [])
                if not issues:
                    break

                all_issues.extend(issues)

                next_page_token = response.get('nextPageToken')
                logger.debug(f"Fetched {len(all_issues)} tickets so far, nextPageToken={bool(next_page_token)}")

                if not next_page_token or len(issues) < max_results:
                    break

            # Transform to required format
            tickets = []
            for issue in all_issues:
                assignee_field = issue['fields'].get('assignee')
                assignee_name  = assignee_field.get('displayName', 'Unassigned') if assignee_field else 'Unassigned'
                assignee_email = (assignee_field.get('emailAddress') or '') if assignee_field else ''

                # For QA filters, override assignee with QA Tester if available
                if qa_field_id:
                    qa_field = issue['fields'].get(qa_field_id)
                    if qa_field:
                        assignee_name  = qa_field.get('displayName', assignee_name)
                        assignee_email = qa_field.get('emailAddress') or ''

                issuetype_field = issue['fields'].get('issuetype')
                issue_type = issuetype_field.get('name', '') if issuetype_field else ''

                ticket = {
                    'ticket_id': issue['key'],
                    'title': issue['fields'].get('summary', ''),
                    'status': issue['fields']['status']['name'],
                    'assignee': assignee_name,
                    'assignee_email': assignee_email,
                    'issue_type': issue_type,
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
