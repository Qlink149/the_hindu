from pydantic import BaseModel
from typing import Dict

class DashboardStats(BaseModel):
    total_leads: int
    hot_leads: int
    warm_leads: int
    attending_leads: int
    interested_leads: int
    site_visits_scheduled: int
    lost_leads: int
    not_attending_leads: int
    qualified_leads: int = 0
    total_calls: int = 0
    total_billed_minutes: int = 0
    avg_call_duration: int = 0
    attending_calls: int = 0
    not_attending_calls: int = 0
    dropped_calls: int = 0
    busy_calls: int = 0
    na_calls: int = 0
    wrong_number_calls: int = 0
    lead_status_stats: Dict[str, int]
    lead_source_stats: Dict[str, int]
    regional_demand: Dict[str, int]
    budget_distribution: Dict[str, int]
    disposition_stats: Dict[str, int] = {}
    disposition_avg_duration: Dict[str, float] = {}
