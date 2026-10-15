"""Jinja filters shared by every template."""

from airline.utils import money, money_short, parse_datetime


class TemplateFilters:
    @staticmethod
    def register(app):
        filters = TemplateFilters()
        for name in ("money", "money_short", "pct", "nice_date", "nice_time", "day_month", "weekday", "relative_days"):
            app.jinja_env.filters[name] = getattr(filters, name)

    @staticmethod
    def money(value):
        return money(value or 0).replace(".00", "")

    @staticmethod
    def money_short(value):
        return money_short(value or 0)

    @staticmethod
    def pct(value, digits=0):
        return f"{(value or 0) * 100:.{digits}f}%"

    @staticmethod
    def nice_date(value):
        return parse_datetime(value).strftime("%a %d %b")

    @staticmethod
    def nice_time(value):
        return parse_datetime(value).strftime("%H:%M")

    @staticmethod
    def day_month(value):
        return parse_datetime(value).strftime("%d %b")

    @staticmethod
    def weekday(value):
        return parse_datetime(value).strftime("%A")

    @staticmethod
    def relative_days(value):
        from airline.utils import now
        days = (parse_datetime(value).date() - now().date()).days
        if days == 0:
            return "Today"
        if days == 1:
            return "Tomorrow"
        if days == -1:
            return "Yesterday"
        return f"In {days} days" if days > 0 else f"{-days} days ago"
