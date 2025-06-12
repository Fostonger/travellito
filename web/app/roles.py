from enum import Enum

class Role(str, Enum):
    """Enumerates every role recognised by the platform.

    Using an Enum avoids typos when referring to roles across the code-base
    while still being JSON-serialisable (inherits from *str*).
    """

    admin = "admin"
    agency = "agency"
    landlord = "landlord"
    bot_user = "bot_user"
    bot = "bot"
    manager = "manager" 