"""Names for new passkeys, from the browser and device that made them (FR-12.6)."""

# Checked in order: several browsers carry another's token too (Edge and Opera
# say "Chrome", Chrome says "Safari").
_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Windows", "Windows"),
    ("Linux", "Linux"),
)


def passkey_name(user_agent: str | None) -> str:
    """
    A name for a new passkey, from the browser and device that made it
    (FR-12.6), such as "Chrome on macOS".
    """
    agent = user_agent or ""
    browser = next((name for token, name in _BROWSERS if token in agent), None)
    system = next((name for token, name in _SYSTEMS if token in agent), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "Passkey"
