"""SpendMeter — usage/spend tracking and degrade-before-cap (FR-38, FR-53, AD-19).

Every ``llm_call`` and transcription call writes a row with ``est_cost_usd``
(Consistency Conventions → "LLM call logging"). This rolls those up, projects
month-end spend linearly from month-to-date, and decides throttle state.

The credit is a **hard cap** (VS Enterprise $150/mo): if it is exhausted the whole
Azure subscription is disabled until the next period, taking the daily quiz
offline too. So throttling is not an optimisation — above ``throttle_at_pct`` the
worker stops taking new ingestion while the quiz keeps running.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime

from quizme.application.config import BudgetConfig
from quizme.application.ports import Clock, Store


@dataclass(slots=True)
class SpendMeterImpl:
    store: Store
    clock: Clock
    budget: BudgetConfig

    def month_to_date_usd(self) -> float:
        now = self.clock.now()
        return self.store.month_spend_usd(year=now.year, month=now.month)

    def projected_month_end_usd(self) -> float:
        now = self.clock.now()
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        elapsed = _fractional_day_of_month(now)
        mtd = self.month_to_date_usd()
        if elapsed <= 0:
            return mtd
        return mtd / elapsed * days_in_month

    def is_throttled(self) -> bool:
        cap = self.budget.monthly_credit_usd
        threshold = cap * self.budget.throttle_at_pct / 100.0
        return self.projected_month_end_usd() >= threshold

    def should_warn(self) -> bool:
        cap = self.budget.monthly_credit_usd
        return self.projected_month_end_usd() >= cap * self.budget.warn_at_pct / 100.0


def _fractional_day_of_month(now: datetime) -> float:
    return (now.day - 1) + (now.hour * 3600 + now.minute * 60 + now.second) / 86400.0
