from ..comparison_level_library import (  # noqa: F401
    _mutable_params,
    exact_match_level,
    levenshtein_level,
    jaccard_level,
    JaroWinklerLevelBase,
    else_level,
    null_level,
    distance_function_level,
    columns_reversed_level,
    distance_in_km_level,
    percentage_difference_level,
    ArrayIntersectLevelBase,
)


def size_array_intersect_sql(col_name_l, col_name_r):
    # sum of individual (unique) array sizes, minus the (unique) union
    return (
        f"list_unique({col_name_l}) + list_unique({col_name_r})"
        f" - list_unique(list_concat({col_name_l}, {col_name_r}))"
    )


_mutable_params["dialect"] = "duckdb"


class DuckDBLevel():

    @property
    def _sql_dialect(self):
        return "duckdb"

    @property
    def _size_array_intersect_function(self):
        return size_array_intersect_sql

    @property
    def _jaro_winkler_name(self):
        return "jaro_winkler_similarity"


class jaro_winkler_level(DuckDBLevel, JaroWinklerLevelBase):
    pass

class array_intersect_level(DuckDBLevel, ArrayIntersectLevelBase):
    pass
