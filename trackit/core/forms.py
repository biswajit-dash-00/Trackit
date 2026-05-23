"""Django forms for TrackIt"""
from django import forms
from core.models import Filter


class FilterForm(forms.ModelForm):
    """Form for creating and editing filters"""
    
    class Meta:
        model = Filter
        fields = [
            'name',
            'jira_filter_id',
            'admin_email',
            'active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter filter name (e.g., "Backend Sprint Tasks")',
                'required': True,
            }),
            'jira_filter_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Jira filter ID (e.g., 10234)',
                'required': True,
            }),
            'admin_email': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. alice@company.com, bob@company.com',
                'rows': 2,
                'required': True,
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
    
    def clean_jira_filter_id(self):
        """Validate Jira filter ID"""
        jira_filter_id = self.cleaned_data.get('jira_filter_id', '').strip()
        if not jira_filter_id:
            raise forms.ValidationError('Jira filter ID is required.')
        if not jira_filter_id.isdigit():
            raise forms.ValidationError('Jira filter ID must be numeric.')
        return jira_filter_id
    
    def clean_admin_email(self):
        """Validate one or more comma-separated admin emails"""
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        raw = self.cleaned_data.get('admin_email', '')
        emails = [e.strip().lower() for e in raw.split(',') if e.strip()]
        if not emails:
            raise forms.ValidationError('At least one admin email is required.')
        invalid = []
        for email in emails:
            try:
                validate_email(email)
            except DjangoValidationError:
                invalid.append(email)
        if invalid:
            raise forms.ValidationError(f'Invalid email address(es): {", ".join(invalid)}')
        return ', '.join(emails)
