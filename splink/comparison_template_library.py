# Script defining comparison templates that act as wrapper functions which produce
# comparisons based on the type of data in a column with default values to make
# it simpler to use splink out-of-the-box

from __future__ import annotations

import logging

from .comparison import Comparison  # change to self
from .comparison_library_utils import (
    datediff_error_logger,
    distance_threshold_comparison_levels,
    distance_threshold_description,
)
from .input_column import InputColumn
from .misc import ensure_is_iterable

logger = logging.getLogger(__name__)


class DateComparisonBase(Comparison):
    def __init__(
        self,
        col_name: str,
        valid_string_regex: str = None,
        include_exact_match_level: bool = True,
        term_frequency_adjustments: bool = False,
        separate_1st_january: bool = False,
        levenshtein_thresholds: int | list = [1, 2],
        jaro_thresholds: int | list = [],
        jaro_winkler_thresholds: int | list = [],
        datediff_thresholds: int | list = [1, 10],
        datediff_metrics: str | list = ["year", "year"],
        m_probability_exact_match: float = None,
        m_probability_1st_january: float = None,
        m_probability_or_probabilities_lev: float | list = None,
        m_probability_or_probabilities_jar: float | list = None,
        m_probability_or_probabilities_jw: float | list = None,
        m_probability_or_probabilities_datediff: float | list = None,
        m_probability_else: float = None,
        cast_strings_to_date: bool = False,
        date_format: str = None,
    ) -> Comparison:
        """A wrapper to generate a comparison for a date column the data in
        `col_name` with preselected defaults.

        The default arguments will give a comparison with comparison levels:\n
        - Exact match (1st of January only)\n
        - Exact match (all other dates)\n
        - Levenshtein distance <= 2\n
        - Date difference <= 1 year\n
        - Date difference <= 10 years \n
        - Anything else

        Args:
            col_name (str): The name of the column to compare.
            valid_string_regex (str): regular expression pattern that if not
                matched will result in column being treated as a null.
            include_exact_match_level (bool, optional): If True, include an exact match
                level. Defaults to True.
            term_frequency_adjustments (bool, optional): If True, apply term frequency
                adjustments to the exact match level. Defaults to False.
            separate_1st_january (bool, optional): If True, include a separate
                exact match comparison level when date is 1st January.
            levenshtein_thresholds (Union[int, list], optional): The thresholds to use
                for levenshtein similarity level(s).
                We recommend using one of either levenshtein, jaro or jaro_winkler for
                fuzzy matching, but not multiple.
                Defaults to [2]
            jaro_thresholds (Union[int, list], optional): The thresholds to use
                for jaro similarity level(s).
                We recommend using one of either levenshtein, jaro or jaro_winkler for
                fuzzy matching, but not multiple.
                Defaults to []
            jaro_winkler_thresholds (Union[int, list], optional): The thresholds to use
                for jaro_winkler similarity level(s).
                We recommend using one of either levenshtein, jaro or jaro_winkler for
                fuzzy matching, but not multiple.
                Defaults to []
            datediff_thresholds (Union[int, list], optional): The thresholds to use
                for datediff similarity level(s).
                Defaults to [1, 1].
            datediff_metrics (Union[str, list], optional): The metrics to apply
                thresholds to for datediff similarity level(s).
                Defaults to ["month", "year"].
            m_probability_exact_match (_type_, optional): If provided, overrides the
                default m probability for the exact match level. Defaults to None.
            m_probability_or_probabilities_lev (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the levenshtein thresholds specified. Defaults to None.
            m_probability_or_probabilities_jar (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the jaro thresholds specified. Defaults to None.
            m_probability_or_probabilities_jw (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the jaro winkler thresholds specified. Defaults to None.
            m_probability_or_probabilities_datediff (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the datediff thresholds specified. Defaults to None.
            m_probability_else (_type_, optional): If provided, overrides the
                default m probability for the 'anything else' level. Defaults to None.
            cast_strings_to_date (bool, optional): Set to True to
                enable date-casting when input dates are strings. Also adjust
                date_format if date-strings are not in (yyyy-mm-dd) format.
                Defaults to False.
            date_format(str, optional): Format of input dates if date-strings
                are given. Must be consistent across record pairs. If None
                (the default), downstream functions for each backend assign
                date_format to ISO 8601 format (yyyy-mm-dd).


        Examples:
            >>> # DuckDB Basic Date Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.date_comparison("date_of_birth")

            >>> # DuckDB Bespoke Date Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.date_comparison(
            >>>                     "date_of_birth",
            >>>                     levenshtein_thresholds=[],
            >>>                     jaro_winkler_thresholds=[0.88],
            >>>                     datediff_thresholds=[1, 1],
            >>>                     datediff_metrics=["month", "year"])

            >>> # Spark Basic Date Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.date_comparison("date_of_birth")

            >>> # Spark Bespoke Date Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.date_comparison(
            >>>                     "date_of_birth",
            >>>                     levenshtein_thresholds=[],
            >>>                     jaro_winkler_thresholds=[0.88],
            >>>                     datediff_thresholds=[1, 1],
            >>>                     datediff_metrics=["month", "year"])

        Returns:
            Comparison: A comparison that can be inclued in the Splink settings
                dictionary.
        """
        # Construct Comparison
        comparison_levels = []
        comparison_levels.append(self._null_level(col_name, valid_string_regex))

        # Validate user inputs
        datediff_error_logger(thresholds=datediff_thresholds, metrics=datediff_metrics)

        if separate_1st_january:
            comparison_level = {
                "sql_condition": f"""{col_name}_l = {col_name}_r AND
                                    substr({col_name}_l, 6, 5) = '01-01'""",
                "label_for_charts": "Matching and 1st Jan",
            }
            if m_probability_1st_january:
                comparison_level["m_probability"] = m_probability_1st_january
            if term_frequency_adjustments:
                comparison_level["tf_adjustment_column"] = col_name
            comparison_levels.append(comparison_level)

        if include_exact_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                term_frequency_adjustments=term_frequency_adjustments,
                m_probability=m_probability_exact_match,
            )
            comparison_levels.append(comparison_level)

        levenshtein_thresholds = ensure_is_iterable(levenshtein_thresholds)
        if len(levenshtein_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "levenshtein",
                levenshtein_thresholds,
                m_probability_or_probabilities_lev,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        jaro_thresholds = ensure_is_iterable(jaro_thresholds)
        if len(jaro_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "jaro",
                jaro_thresholds,
                m_probability_or_probabilities_jar,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        jaro_winkler_thresholds = ensure_is_iterable(jaro_winkler_thresholds)
        if len(jaro_winkler_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "jaro-winkler",
                jaro_winkler_thresholds,
                m_probability_or_probabilities_jw,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        count_string_match_functions_used = (
            (len(levenshtein_thresholds) > 0)
            + (len(jaro_thresholds) > 0)
            + (len(jaro_winkler_thresholds) > 0)
        )
        if count_string_match_functions_used > 1:
            logger.warning(
                "You have included a comparison level for more than one of "
                "Levenshtein, Jaro and Jaro-Winkler similarity. We recommend "
                "choosing one of the three."
            )

        datediff_thresholds = ensure_is_iterable(datediff_thresholds)
        datediff_metrics = ensure_is_iterable(datediff_metrics)
        if len(datediff_thresholds) > 0:
            if m_probability_or_probabilities_datediff is None:
                m_probability_or_probabilities_datediff = [None] * len(
                    datediff_thresholds
                )
            m_probability_or_probabilities_datediff = ensure_is_iterable(
                m_probability_or_probabilities_datediff
            )

            for thres, metric, m_prob in zip(
                datediff_thresholds,
                datediff_metrics,
                m_probability_or_probabilities_datediff,
            ):
                comparison_level = self._datediff_level(
                    col_name,
                    date_threshold=thres,
                    date_metric=metric,
                    m_probability=m_prob,
                    cast_strings_to_date=cast_strings_to_date,
                    date_format=date_format,
                )
                comparison_levels.append(comparison_level)

            comparison_levels.append(
                self._else_level(m_probability=m_probability_else),
            )

        # Construct Description
        comparison_desc = ""
        if include_exact_match_level:
            comparison_desc += "Exact match vs. "

        if len(levenshtein_thresholds) > 0:
            desc = distance_threshold_description(
                col_name, "levenshtein", levenshtein_thresholds
            )
            comparison_desc += desc

        if len(jaro_thresholds) > 0:
            desc = distance_threshold_description(col_name, "jaro", jaro_thresholds)
            comparison_desc += desc

        if len(jaro_winkler_thresholds) > 0:
            desc = distance_threshold_description(
                col_name, "jaro_winkler", jaro_winkler_thresholds
            )
            comparison_desc += desc

        if len(datediff_thresholds) > 0:
            datediff_desc = ", ".join(
                [
                    f"{m.title()}(s): {v}"
                    for v, m in zip(datediff_thresholds, datediff_metrics)
                ]
            )
            plural = "" if len(datediff_thresholds) == 1 else "s"
            comparison_desc += (
                f"Dates within the following threshold{plural} {datediff_desc} vs. "
            )

        comparison_desc += "anything else"

        comparison_dict = {
            "comparison_description": comparison_desc,
            "comparison_levels": comparison_levels,
        }
        super().__init__(comparison_dict)

    @property
    def _is_distance_subclass(self):
        return False


class NameComparisonBase(Comparison):
    def __init__(
        self,
        col_name: str,
        valid_string_regex: str = None,
        include_exact_match_level: bool = True,
        phonetic_col_name: str = None,
        term_frequency_adjustments_name: bool = False,
        term_frequency_adjustments_phonetic_name: bool = False,
        levenshtein_thresholds: int | list = [],
        jaro_thresholds: float | list = [],
        jaro_winkler_thresholds: float | list = [0.95, 0.88],
        jaccard_thresholds: float | list = [],
        m_probability_exact_match_name: bool = None,
        m_probability_exact_match_phonetic_name: bool = None,
        m_probability_or_probabilities_lev: float | list = None,
        m_probability_or_probabilities_jar: float | list = None,
        m_probability_or_probabilities_jw: float | list = None,
        m_probability_or_probabilities_jac: float | list = None,
        m_probability_else: float = None,
    ) -> Comparison:
        """A wrapper to generate a comparison for a name column the data in
        `col_name` with preselected defaults.

        The default arguments will give a comparison with comparison levels:\n
        - Exact match \n
        - Jaro Winkler similarity >= 0.95\n
        - Jaro Winkler similarity >= 0.88\n
        - Anything else

        Args:
            col_name (str): The name of the column to compare.
            valid_string_regex (str): regular expression pattern that if not
                matched will result in column being treated as a null.
            include_exact_match_level (bool, optional): If True, include an exact match
                level for col_name. Defaults to True.
            phonetic_col_name (str): The name of the column with phonetic reduction
                (such as dmetaphone) of col_name. Including parameter will create
                an exact match level for  phonetic_col_name. The phonetic column must
                be present in the dataset to use this parameter.
                Defaults to None
            term_frequency_adjustments_name (bool, optional): If True, apply term
                frequency adjustments to the exact match level for "col_name".
                Defaults to False.
            term_frequency_adjustments_phonetic_name (bool, optional): If True, apply
                term frequency adjustments to the exact match level for
                "phonetic_col_name".
                Defaults to False.
            levenshtein_thresholds (Union[int, list], optional): The thresholds to use
                for levenshtein similarity level(s).
                Defaults to []
            jaro_thresholds (Union[int, list], optional): The thresholds to use
                for jaro similarity level(s).
                We recommend using one of either levenshtein, jaro or jaro_winkler for
                fuzzy matching, but not multiple.
                Defaults to []
            jaro_winkler_thresholds (Union[int, list], optional): The thresholds to use
                for jaro_winkler similarity level(s).
                Defaults to [0.88]
            jaccard_thresholds (Union[int, list], optional): The thresholds to use
                for jaccard similarity level(s).
                Defaults to []
            m_probability_exact_match_name (_type_, optional): If provided, overrides
                the default m probability for the exact match level for col_name.
                Defaults to None.
            m_probability_exact_match_phonetic_name (_type_, optional): If provided,
                overrides the default m probability for the exact match level for
                phonetic_col_name. Defaults to None.
            m_probability_or_probabilities_lev (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the thresholds specified. Defaults to None.
            m_probability_or_probabilities_jar (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the jaro thresholds specified. Defaults to None.
            m_probability_or_probabilities_jw (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the jaro winkler thresholds specified. Defaults to None.
            m_probability_or_probabilities_jac (Union[float, list], optional):
                If provided, overrides the default m probabilities
                for the jaccard thresholds specified. Defaults to None.
            m_probability_else (_type_, optional): If provided, overrides the
                default m probability for the 'anything else' level. Defaults to None.

        Examples:
            >>> # DuckDB Basic Name Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.name_comparison("name")

            >>> # DuckDB Bespoke Name Comparison
            >>> import splink.duckdb.duckdb_comparison_template_library as ctl
            >>> clt.name_comparison("name",
            >>>                     phonetic_col_name = "name_dm",
            >>>                     term_frequency_adjustments_name = True,
            >>>                     levenshtein_thresholds=[2],
            >>>                     jaro_winkler_thresholds=[],
            >>>                     jaccard_thresholds=[1]
            >>>                     )

            >>> # Spark Basic Name Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.name_comparison("name")

            >>> # Spark Bespoke Date Comparison
            >>> import splink.spark.spark_comparison_template_library as ctl
            >>> clt.name_comparison("name",
            >>>                     phonetic_col_name = "name_dm",
            >>>                     term_frequency_adjustments_name = True,
            >>>                     levenshtein_thresholds=[2],
            >>>                     jaro_winkler_thresholds=[],
            >>>                     jaccard_thresholds=[1]
            >>>                     )

        Returns:
            Comparison: A comparison that can be included in the Splink settings
                dictionary.
        """

        # Construct Comparison
        comparison_levels = []
        comparison_levels.append(self._null_level(col_name, valid_string_regex))

        if include_exact_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                term_frequency_adjustments=term_frequency_adjustments_name,
                m_probability=m_probability_exact_match_name,
                include_colname_in_charts_label=True,
            )
            comparison_levels.append(comparison_level)

            if phonetic_col_name is not None:
                comparison_level = self._exact_match_level(
                    phonetic_col_name,
                    term_frequency_adjustments=term_frequency_adjustments_phonetic_name,
                    m_probability=m_probability_exact_match_phonetic_name,
                    include_colname_in_charts_label=True,
                )
                comparison_levels.append(comparison_level)

        levenshtein_thresholds = ensure_is_iterable(levenshtein_thresholds)
        if len(levenshtein_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "levenshtein",
                levenshtein_thresholds,
                m_probability_or_probabilities_lev,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        jaro_thresholds = ensure_is_iterable(jaro_thresholds)
        if len(jaro_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "jaro",
                jaro_thresholds,
                m_probability_or_probabilities_jar,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        jaro_winkler_thresholds = ensure_is_iterable(jaro_winkler_thresholds)
        if len(jaro_winkler_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "jaro-winkler",
                jaro_winkler_thresholds,
                m_probability_or_probabilities_jw,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        jaccard_thresholds = ensure_is_iterable(jaccard_thresholds)
        if len(jaccard_thresholds) > 0:
            threshold_comparison_levels = distance_threshold_comparison_levels(
                self,
                col_name,
                "jaccard",
                jaccard_thresholds,
                m_probability_or_probabilities_jar,
            )
            comparison_levels = comparison_levels + threshold_comparison_levels

        comparison_levels.append(
            self._else_level(m_probability=m_probability_else),
        )

        # Construct Description
        comparison_desc = ""
        if include_exact_match_level:
            comparison_desc += "Exact match vs. "

        if phonetic_col_name is not None:
            comparison_desc += "Names with phonetic exact match vs. "

        if len(levenshtein_thresholds) > 0:
            desc = distance_threshold_description(
                col_name, "levenshtein", levenshtein_thresholds
            )
            comparison_desc += desc

        if len(jaro_thresholds) > 0:
            desc = distance_threshold_description(col_name, "jaro", jaro_thresholds)
            comparison_desc += desc

        if len(jaro_winkler_thresholds) > 0:
            desc = distance_threshold_description(
                col_name, "jaro_winkler", jaro_winkler_thresholds
            )
            comparison_desc += desc

        if len(jaccard_thresholds) > 0:
            desc = distance_threshold_description(
                col_name, "jaccard", jaccard_thresholds
            )
            comparison_desc += desc

        comparison_desc += "anything else"

        comparison_dict = {
            "comparison_description": comparison_desc,
            "comparison_levels": comparison_levels,
        }
        super().__init__(comparison_dict)

    @property
    def _is_distance_subclass(self):
        return False


class PostcodeComparisonBase(Comparison):
    def __init__(
        self,
        col_name: str,
        regex_extract: str = None,
        valid_string_regex: str = None,
        include_full_match_level=True,
        include_sector_match_level=True,
        include_district_match_level=True,
        include_area_match_level=True,
        include_distance_in_km_level=False,
        lat_col: str = None,
        long_col: str = None,
        km_threshold: int | float = None,
        term_frequency_adjustments=False,
        m_probability_full_match=None,
        m_probability_sector_match=None,
        m_probability_district_match=None,
        m_probability_area_match=None,
        m_probability_distance_in_km=None,
        # m_probability_or_probabilities_sizes: Union[float, list] = None,
        m_probability_else=None,
    ) -> Comparison:
        """A wrapper to generate a comparison for a poscode column 'col_name'
            with preselected defaults.

        The default arguments will give a comparison with levels:\n
        - Exact match on full postcode\n
        - Exact match on sector\n
        - Exact match on district\n
        - Exact match on area\n
        - All other comparisons

        Args:
            col_name (str): The name of the column to compare.
            regex_extract (str): Regular expression pattern to evaluate a match on.
            valid_string_regex (str): regular expression pattern that if not
                matched will result in column being treated as a null.
            include_full_match_level (bool, optional): If True, include an exact
                match on full postcode level. Defaults to True.
            include_sector_match_level (bool, optional): If True, include an exact
                match on sector level. Defaults to True.
            include_district_match_level (bool, optional): If True, include an exact
                match on district level. Defaults to True.
            include_area_match_level (bool, optional): If True, include an exact
                match on area level. Defaults to True.
            include_distance_in_km_level (bool, optional): If True, include a
                comparison of distance between postcodes as measured in kilometers.
                Defaults to False.
            lat_col (str): The name of a latitude column or the respective array
                or struct column column containing the information, plus an index.
                For example: long_lat['lat'] or long_lat[0].
            long_col (str): The name of a longitudinal column or the respective array
                or struct column column containing the information, plus an index.
                For example: long_lat['long'] or long_lat[1].
            km_threshold (int): The total distance in kilometers to evaluate the
                distance_in_km_level comparison against.
            term_frequency_adjustments (bool, optional): If True, apply term frequency
                adjustments to the full postcode exact match level. Defaults to False.
            m_probability_full_match (_type_, optional): If provided, overrides
                the default m probability for the full postcode exact match level
                for col_name. Defaults to None.
            m_probability_sector_match (_type_, optional): If provided, overrides
                the default m probability for the sector exact match level
                for col_name. Defaults to None.
            m_probability_district_match (_type_, optional): If provided, overrides
                the default m probability for the district exact match level for
                col_name. Defaults to None.
            m_probability_area_match (_type_, optional): If provided, overrides
                the default m probability for the area exact match level for
                col_name. Defaults to None.
            m_probability_else (_type_, optional): If provided, overrides the
                default m probability for the 'anything else' level. Defaults to None.

        Returns:
            Comparison: A comparison that can be inclued in the Splink settings
                dictionary.
        """

        postcode_col = InputColumn(col_name, sql_dialect=self._sql_dialect)
        postcode_col_l, postcode_col_r = postcode_col.names_l_r()

        comparison_levels = []
        comparison_levels.append(self._null_level(col_name, valid_string_regex))

        if include_full_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                regex_extract=None,
                term_frequency_adjustments=term_frequency_adjustments,
                m_probability=m_probability_full_match,
                include_colname_in_charts_label=True,
            )
            comparison_levels.append(comparison_level)

        if include_sector_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                regex_extract="^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9]",
                m_probability=m_probability_sector_match,
            )
            comparison_levels.append(comparison_level)

        if include_district_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                regex_extract="^[A-Z]{1,2}[0-9][A-Z0-9]?",
                m_probability=m_probability_district_match,
            )
            comparison_levels.append(comparison_level)

        if include_area_match_level:
            comparison_level = self._exact_match_level(
                col_name,
                regex_extract="^[A-Z]{1,2}",
                m_probability=m_probability_area_match,
            )
            comparison_levels.append(comparison_level)

        if include_distance_in_km_level:
            comparison_level = self._distance_in_km_level(
                lat_col,
                long_col,
                km_threshold,
                m_probability=m_probability_distance_in_km,
            )
            comparison_levels.append(comparison_level)

        comparison_levels.append(
            self._else_level(m_probability=m_probability_else),
        )

        # Construct Description
        comparison_desc = ""
        if include_full_match_level:
            comparison_desc += "Exact match on full postcode vs. "

        if include_sector_match_level:
            comparison_desc += "exact match on sector vs. "

        if include_district_match_level:
            comparison_desc += "exact match on district vs. "

        if include_area_match_level:
            comparison_desc += "exact match on area vs. "

        if include_distance_in_km_level:
            comparison_desc += f"distance less than {km_threshold}km vs. "

        comparison_desc += "all other comparisons"

        comparison_dict = {
            "output_column_name": col_name,
            "comparison_description": comparison_desc,
            "comparison_levels": comparison_levels,
        }
        super().__init__(comparison_dict)
