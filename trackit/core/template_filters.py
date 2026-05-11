"""Custom template filters for TrackIt"""

from django import template

register = template.Library()


@register.filter
def dict_lookup(dict_obj, key):
    """
    Look up a value in a dictionary using a key.
    
    Usage in template:
        {{ my_dict|dict_lookup:my_key }}
    """
    if isinstance(dict_obj, dict):
        return dict_obj.get(key)
    return None


@register.filter
def get_item(obj, key):
    """
    Alternative name for dict_lookup.
    Get an item from a dictionary or list using a key/index.
    
    Usage in template:
        {{ my_dict|get_item:my_key }}
    """
    try:
        if isinstance(obj, dict):
            return obj.get(key)
        elif isinstance(obj, (list, tuple)):
            return obj[int(key)]
        return None
    except (KeyError, ValueError, IndexError, TypeError):
        return None
