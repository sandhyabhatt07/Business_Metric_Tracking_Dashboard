"""Raw-layer table definitions.

App DB tables keep the source's types. CRM, ad spend and FX land as text exactly as received, so that
every parsing rule lives in one reviewed place: the dbt staging models.
"""

from dataclasses import dataclass, field

LOAD_COLUMNS = [("_batch_id", "STRING"), ("_loaded_at", "TIMESTAMP")]


@dataclass(frozen=True)
class RawTable:
    name: str
    columns: list[tuple[str, str]]
    # "replace" reloads the whole table each run; "append" adds a new batch.
    mode: str = "replace"
    partition_by: str | None = None
    cluster_by: list[str] = field(default_factory=list)

    @property
    def all_columns(self) -> list[tuple[str, str]]:
        return self.columns + LOAD_COLUMNS


RAW_TABLES = {t.name: t for t in [
    RawTable("app_accounts", [
        ("account_id", "INT64"), ("workspace_name", "STRING"), ("owner_user_id", "INT64"),
        ("country", "STRING"), ("signup_channel", "STRING"), ("created_at", "TIMESTAMP")]),
    RawTable("app_users", [
        ("user_id", "INT64"), ("account_id", "INT64"), ("email", "STRING"), ("role", "STRING"),
        ("signup_channel", "STRING"), ("onboarding_flow", "STRING"), ("primary_platform", "STRING"),
        ("created_at", "TIMESTAMP")]),
    RawTable("app_subscriptions", [
        ("subscription_id", "INT64"), ("account_id", "INT64"), ("plan", "STRING"),
        ("billing_interval", "STRING"), ("seats", "INT64"), ("unit_price_minor", "INT64"),
        ("discount_pct", "FLOAT64"), ("currency", "STRING"), ("status", "STRING"),
        ("cancel_reason", "STRING"), ("started_at", "TIMESTAMP"), ("ended_at", "TIMESTAMP")]),
    RawTable("app_invoices", [
        ("invoice_id", "INT64"), ("account_id", "INT64"), ("subscription_id", "INT64"),
        ("status", "STRING"), ("amount_minor", "INT64"), ("currency", "STRING"),
        ("period_start", "TIMESTAMP"), ("period_end", "TIMESTAMP"), ("issued_at", "TIMESTAMP")]),
    RawTable("app_experiment_assignments", [
        ("user_id", "INT64"), ("experiment_name", "STRING"), ("variant", "STRING"),
        ("assigned_at", "TIMESTAMP")]),
    RawTable("app_events", [
        ("event_id", "INT64"), ("user_id", "INT64"), ("session_id", "INT64"), ("event_name", "STRING"),
        ("event_ts", "TIMESTAMP"), ("received_at", "TIMESTAMP"), ("platform", "STRING"),
        ("app_version", "STRING")],
        mode="append", partition_by="received_at", cluster_by=["event_name", "user_id"]),
    RawTable("crm_companies", [
        ("crm_company_id", "STRING"), ("name", "STRING"), ("app_account_id", "STRING"),
        ("segment", "STRING"), ("numberofemployees", "STRING"), ("industry", "STRING"),
        ("region", "STRING"), ("country", "STRING"), ("hubspot_owner", "STRING"),
        ("lifecyclestage", "STRING"), ("createdate", "STRING"), ("lastmodifieddate", "STRING"),
        ("_raw", "STRING")]),
    RawTable("ad_spend", [
        ("date", "STRING"), ("platform", "STRING"), ("campaign", "STRING"), ("impressions", "STRING"),
        ("clicks", "STRING"), ("spend", "STRING"), ("currency", "STRING"), ("_source_file", "STRING"),
        ("_source_line", "INT64")]),
    RawTable("fx_rates", [
        ("rate_date", "STRING"), ("base_currency", "STRING"), ("currency", "STRING"), ("rate", "STRING")]),
]}
