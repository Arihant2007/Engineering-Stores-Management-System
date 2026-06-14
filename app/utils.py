from datetime import datetime, date
import locale


def format_currency(value):
    try:
        return f"Rs. {float(value):,.2f}"
    except (TypeError, ValueError):
        return "Rs. 0.00"


def format_datetime(value, fmt='%d-%b-%Y %H:%M'):
    if value is None:
        return '-'
    if isinstance(value, str):
        return value
    return value.strftime(fmt)


def format_date(value, fmt='%d-%b-%Y'):
    if value is None:
        return '-'
    if isinstance(value, str):
        return value
    return value.strftime(fmt)
