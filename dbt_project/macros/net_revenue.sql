{%- macro net_revenue(gross_col, discount_col) -%}
    round({{ gross_col }} - coalesce({{ discount_col }}, 0), 2)
{%- endmacro -%}
