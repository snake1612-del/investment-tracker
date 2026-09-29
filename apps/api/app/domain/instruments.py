"""Manual Instrument name rules from Decision 010."""


class InvalidInstrument(ValueError):
    """A manual Instrument name is invalid."""


def normalized_instrument_name(name: str) -> str:
    trimmed = name.strip()
    if not 1 <= len(trimmed) <= 200:
        raise InvalidInstrument("Instrument name must contain 1 to 200 characters after trimming")
    return trimmed
