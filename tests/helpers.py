from datetime import date

from nse_agent.fundamentals import Period


def period(ticker="TEST", year=2024, **values) -> Period:
    return Period(ticker=ticker, period=f"FY{year}", period_end=date(year, 12, 31),
                  published=date(year + 1, 3, 31), type="annual", source_url="https://example.test/r.pdf",
                  values=values)
