{# Use the configured schema name as-is (staging, core, metrics...) instead of prefixing the target's. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
