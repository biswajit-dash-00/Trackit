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
            'admin_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Admin email for notifications',
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
        """Validate admin email"""
        admin_email = self.cleaned_data.get('admin_email', '').strip().lower()
        if not admin_email:
            raise forms.ValidationError('Admin email is required.')
        
        # Check for duplicate emails (but allow current instance's email in edit mode)
        existing = Filter.objects.filter(admin_email=admin_email)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(f'A filter with this admin email already exists.')
        
        return admin_email
