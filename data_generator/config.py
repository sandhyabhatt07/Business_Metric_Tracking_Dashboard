"""Run-time settings for the synthetic data generator."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Config:
    start_date: date = date(2024, 10, 1)
    end_date: date = date(2026, 9, 30)
    n_accounts: int = 10_000
    n_internal_users: int = 35
    seed: int = 42

    # Onboarding A/B test: "guided_checklist" vs the "classic" flow.
    experiment_name: str = "onboarding_checklist_v1"
    experiment_start: date = date(2026, 2, 2)
    experiment_end: date = date(2026, 4, 27)
    # The winner is rolled out to every new signup from this date on.
    rollout_date: date = date(2026, 5, 11)
    # Absolute lift in P(activated | onboarded) for the guided checklist.
    activation_lift: float = 0.10

    # Incidents planted in the event stream (see docs/data_sources.md).
    outage_date: date = date(2025, 7, 14)
    ios_double_fire_start: date = date(2026, 1, 20)
    ios_double_fire_end: date = date(2026, 1, 22)

    @property
    def n_days(self) -> int:
        return (self.end_date - self.start_date).days + 1
