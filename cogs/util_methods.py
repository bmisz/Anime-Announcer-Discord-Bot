from langdetect import detect
from datetime import datetime
from pathlib import Path


def format_time(
    *, unix_epoch_time: int | None = None, date: str | None = None
) -> str | None:
    """
    Converts either a Unix epoch time or a date string to a human-readable format.

    Args:
        unix_epoch_time (int | None): If specified, the Unix epoch time to convert.
        date (str | None): If specified, the date string to convert ('year-month-day').
    Returns:
        formatted_time (str | None): The human-readable date string if successful, otherwise None.
    Raises:
        ValueError: If both 'unix_epoch_time' and 'date' are specified.
    """

    if unix_epoch_time is not None and date is not None:
        raise ValueError("Specify either 'unix_epoch_time' or 'date', but not both.")
    if unix_epoch_time is None and date is None:
        return None

    if unix_epoch_time is not None:
        dt_obj = datetime.fromtimestamp(unix_epoch_time)
        formatted_time = dt_obj.strftime("%a %d %b, %I:%M%p")
        return formatted_time
    if date is not None:
        # Missing day case (2026-5-None)
        if not date.endswith("None-None") and date.count("None") == 1:
            clean_date = date.replace("-None", "")
            dt = datetime.strptime(clean_date, "%Y-%m")
            return dt.strftime("%B, %Y")

        # Missing month & day case (2026-None-None)
        if date.endswith("None-None"):
            year_only = date.split("-")[0]
            return year_only

        # Full Date Case (2026-5-29)
        dt = datetime.strptime(date, "%Y-%m-%d")
        day_num = dt.day
        ordinal_day = get_ordinal_suffix(day_num)
        return dt.strftime(f"%A, %B {ordinal_day}, %Y")

    return None


def determine_english_title(synonym_list: list[str]) -> str | None:
    """
    Determines if any of the given synonyms are in English.

    Args:
        synonym_list (list[str]): A list of synonyms to check.

    Returns:
        english_title (str | None): The English title if found, otherwise None.
    """
    for synonym in synonym_list:
        language_of_syn = detect(synonym)
        if language_of_syn == "en":
            return synonym
    return None  # No synonyms were in english


def get_ordinal_suffix(n: int) -> str:
    n = int(n)

    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:

        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def filter_ids(rows: list[tuple[int, int]]) -> list[tuple[int, list[int]]]:
    """
    Takes a list of tuples containing anime IDs and user IDs and groups them by anime ID.

    Args:
        rows (list[tuple[int, int]]): A list of tuples containing anime IDs and user IDs.

    Returns:
        list[tuple[int, list[int]]]: A list of tuples containing anime IDs and lists of user IDs.
    """
    grouped_data = {}

    for show_id, user_id in rows:
        if show_id not in grouped_data:
            grouped_data[show_id] = []
        grouped_data[show_id].append(user_id)

    return list(grouped_data.items())


def get_mention_string(users_who_track: list[int]) -> str:
    prefix = "<@"
    suffix = ">"
    final_string = "\n".join([f"{prefix}{user}{suffix}" for user in users_who_track])
    return final_string
    # This would be horrible UX. With more than a couple users tracking the same anime it would create a very long list of <@>s
    # I would probably make a custom role for everyone who tracks one anime so you can just @ the role rather than ever user
    # but im putting this on the backburner for now because this bot is just for me.


def load_query(filename: str) -> str:
    """
    Loads a GraphQL query from a file.

    Args:
        filename (str): The name of the file to load from.

    Returns:
        str: The contents of the file as a string.
    """

    BASE_DIR = Path(__file__).resolve().parent
    TARGET_FILE = BASE_DIR / "graphql" / filename
    return TARGET_FILE.read_text()
