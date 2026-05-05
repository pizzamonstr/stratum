{%- macro date_spine(start_date, end_date) -%}

    with date_spine as (

        {{ dbt_utils.date_spine(
            datepart="day",
            start_date="cast('" ~ start_date ~ "' as date)",
            end_date="cast('" ~ end_date ~ "' as date)"
        ) }}

    )

    select cast(date_day as date) as date_day
    from date_spine

{%- endmacro -%}
