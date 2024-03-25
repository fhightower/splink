from .pipeline import CTEPipeline
from .vertically_concatenate import compute_df_concat


def missingness_sqls(columns, input_tablename):
    sqls = []
    col_template = """
                select
                    count({col_name_escaped}) as non_null_count,
                    '{col_name}' as column_name
                from {input_tablename}"""

    selects = [
        col_template.format(
            col_name_escaped=col.name,
            col_name=col.unquote().name,
            input_tablename=input_tablename,
        )
        for col in columns
    ]

    sql = " union all ".join(selects)

    sqls.append(
        {
            "sql": sql,
            "output_table_name": "null_counts_for_columns",
        }
    )

    sql = f"""
    select
        1.0 - non_null_count/(select cast(count(*) as float)
        from {input_tablename}) as null_proportion,
        (select count(*) from {input_tablename}) - non_null_count as null_count,
        (select count(*) from {input_tablename}) as total_record_count,
        column_name
    from null_counts_for_columns
    """

    sqls.append({"sql": sql, "output_table_name": "missingness_data_for_chart"})

    return sqls


def missingness_data(linker, input_tablename):
    columns = linker._input_columns()
    if input_tablename is None:
        pipeline = CTEPipeline(reusable=False)
        splink_dataframe = compute_df_concat(linker, pipeline)
    else:
        splink_dataframe = linker._table_to_splink_dataframe(
            input_tablename, input_tablename
        )
    pipeline = CTEPipeline([splink_dataframe], reusable=False)
    sqls = missingness_sqls(columns, splink_dataframe.physical_name)
    pipeline.enqueue_list_of_sqls(sqls)

    df = linker.db_api.sql_pipeline_to_splink_dataframe(pipeline)

    return df.as_record_dict()


def completeness_data(linker, input_tablename=None, cols=None):
    sqls = []

    if input_tablename is None:
        pipeline = CTEPipeline(reusable=False)
        df_concat = compute_df_concat(linker, pipeline)
        input_tablename = df_concat.physical_name

    if cols is None:
        cols = linker._settings_obj._columns_used_by_comparisons

    if not (
        source_name := (
            linker._settings_obj.column_info_settings.source_dataset_column_name
        )
    ):
        # Set source dataset to a literal string if dedupe_only
        source_name = "'_a'"

    for col in cols:
        sql = f"""
        (select
            {source_name} as source_dataset,
            '{col}' as column_name,
            count(*) - count({col}) as total_null_rows,
            count(*) as total_rows_inc_nulls,
            cast(count({col})*1.0/count(*) as float) as completeness
        from {input_tablename}
        group by source_dataset
        order by count(*) desc)
        """
        sqls.append(sql)

    sql = " union all ".join(sqls)

    pipeline = CTEPipeline(reusable=False)
    pipeline.enqueue_sql(sql, "__splink__df_all_column_completeness")
    df = linker.db_api.sql_pipeline_to_splink_dataframe(pipeline)

    return df.as_record_dict()
