SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "cvv",
    "credit_card",
    "authorization",
    "api_key",
    "apikey",
    "x-api-key",
    "client_secret",
}


def mask_sensitive_data(data):
    """Mask to handle sensitive data."""
    # Support Pydantic models by converting them to dictionaries before masking
    if hasattr(data, "model_dump"):
        try:
            return mask_sensitive_data(data.model_dump())
        except:
            return str(data)  # Fallback to string if dumping fails

    # Recursively check dictionary keys against the sensitive list
    if isinstance(data, dict):
        masked_dict = {}
        for key, value in data.items():
            # If key matches sensitive list (case-insensitive), hide the value
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                masked_dict[key] = "*******"
            else:
                # Recurse to catch sensitive keys nested deeper in the dictionary
                masked_dict[key] = mask_sensitive_data(value)
        return masked_dict

    # Ensure sensitive items inside lists or tuples are also processed
    elif isinstance(data, (list, tuple)):
        items = []
        for item in data:
            items.append(mask_sensitive_data(item))
        return tuple(items) if isinstance(data, tuple) else items

    # Handle custom class objects (like DB sessions or services)
    elif hasattr(data, "__dict__"):
        module_name = getattr(data, "__module__", "")
        # Only expand data schemas/models; keep internal logic objects as 'obj
        if "app.api.v1.schemas" in module_name or "app.db.models" in module_name:
            return mask_sensitive_data(vars(data))
        else:
            return "obj"
    return data
