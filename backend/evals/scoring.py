"""Score one eval answer: compare result rows with the gold rows, never the SQL text."""

from datetime import date, datetime
from decimal import Decimal

TOLERANCE = Decimal("0.01")
EXPECTED_STATUS = {"ambiguous": "clarify", "refuse": "refused"}


def is_number(value: object) -> bool:
    """True for int, float and Decimal, but not bool."""
    return isinstance(value, int | float | Decimal) and not isinstance(value, bool)


def as_day(value: date) -> date:
    """The calendar day of a date or timestamp."""
    return value.date() if isinstance(value, datetime) else value


def values_equal(gold: object, result: object) -> bool:
    """Numbers within 0.01, text ignoring case, timestamps by day, NULL only with NULL."""
    if gold is None or result is None:
        return gold is None and result is None
    if is_number(gold) and is_number(result):
        return abs(Decimal(str(gold)) - Decimal(str(result))) <= TOLERANCE
    if isinstance(gold, date) and isinstance(result, date):
        return as_day(gold) == as_day(result)
    if isinstance(gold, str) and isinstance(result, str):
        return gold.casefold() == result.casefold()
    return False


def row_matches(gold_row: list, result_row: list) -> bool:
    """Every gold value equals a different value in the result row; extra columns are fine."""
    unused = list(result_row)
    for gold_value in gold_row:
        match = next((i for i, value in enumerate(unused) if values_equal(gold_value, value)), None)
        if match is None:
            return False
        unused.pop(match)
    return True


def results_match(gold_rows: list[list], result_rows: list[list]) -> bool:
    """Same number of rows, and every gold row matches a different result row, in any order."""
    if len(gold_rows) != len(result_rows):
        return False
    unused = list(result_rows)
    for gold_row in gold_rows:
        match = next((i for i, row in enumerate(unused) if row_matches(gold_row, row)), None)
        if match is None:
            return False
        unused.pop(match)
    return True


def wrong_answer_reason(question: dict, audit: dict, config: str) -> str:
    """Why an answered question has the wrong rows: the route, the arguments or the SQL."""
    if config == "full" and question["category"] == "metric":
        chose_expected = (
            audit["path"] == "metric" and audit["metric_id"] == question["expected_metric"]
        )
        return "wrong_args" if chose_expected else "wrong_route"
    if config == "full" and question["category"] == "freeform" and audit["path"] == "metric":
        return "wrong_route"
    return "wrong_result"


def score(
    question: dict, response: dict, gold_rows: list[list] | None, config: str
) -> tuple[bool, str | None]:
    """Whether the response passes, and the failure reason if it does not."""
    status = response["status"]
    expected_status = EXPECTED_STATUS.get(question["category"])
    if expected_status is not None:
        passed = status == expected_status
        return passed, None if passed else "wrong_route"
    if status == "failed":
        return False, response["failure"]["reason"]
    if status != "answered":
        return False, "wrong_route"
    if results_match(gold_rows, response["rows"]):
        return True, None
    return False, wrong_answer_reason(question, response["audit"], config)
