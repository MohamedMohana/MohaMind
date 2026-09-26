def is_configured_key(value: str) -> bool:
    value = value.strip().lower()
    return (
        bool(value)
        and not value.startswith("your-")
        and value
        not in {
            "missing-key",
            "changeme",
            "replace-me",
            "none",
            "null",
        }
    )
