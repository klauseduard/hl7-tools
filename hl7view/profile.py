"""Integration profile loader for custom field name/description overlays."""

import json


def load_profile(path):
    """Load an integration profile JSON file. Returns profile dict."""
    with open(path) as f:
        profile = json.load(f)
    if not isinstance(profile, dict) or 'name' not in profile:
        raise ValueError('Invalid profile: missing "name" field')
    return profile


def get_profile_segment(profile, seg_name):
    """Get profile segment info. Returns dict or None."""
    if not profile or 'segments' not in profile:
        return None
    return profile['segments'].get(seg_name)


def get_profile_field(profile, seg_name, field_num):
    """Get profile field overlay for a segment field. Returns dict or None."""
    seg = get_profile_segment(profile, seg_name)
    if not seg or 'fields' not in seg:
        return None
    return seg['fields'].get(str(field_num))


def get_profile_component(profile, seg_name, field_num, comp_index):
    """Get profile component overlay. Returns dict or None."""
    fld = get_profile_field(profile, seg_name, field_num)
    if not fld or 'components' not in fld:
        return None
    return fld['components'].get(str(comp_index))
