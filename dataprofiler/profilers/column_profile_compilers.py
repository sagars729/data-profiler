from future.utils import with_metaclass
import abc
from collections import OrderedDict

import pandas as pd

from . import DateTimeColumn, IntColumn, FloatColumn, TextColumn
from . import OrderColumn, CategoricalColumn
from . import DataLabelerColumn
from .profiler_options import StructuredOptions

import multiprocessing as mp

class BaseColumnProfileCompiler(with_metaclass(abc.ABCMeta, object)):

    # NOTE: these profilers are ordered. Test functionality if changed.
    _profilers = list()

    def __repr__(self):
        return self.__class__.__name__

    def __init__(self, df_series, options=None):
        if not self._profilers:
            raise NotImplementedError("Must add profilers.")

        self.name = df_series.name
        self._profiles = OrderedDict()
        self._create_profile(df_series, options)

    @property
    @abc.abstractmethod
    def profile(self):
        raise NotImplementedError()

    def _create_profile(self, df_series, options=None):
        """
        Initializes and evaluates all profilers for the given dataframe.
        
        :param df_series: a given column
        :type df_series: pandas.core.series.Series
        :param options: Options for the structured profiler
        :type options: StructuredOptions
        :return: None
        :rtype: None
        """

        if len(self._profilers) == 0:
            return

        # convert all the values to string
        df_series = df_series.apply(str)

        multiprocess_flag = True
        selected_col_profiles = None
        if options and isinstance(options, StructuredOptions):
            selected_col_profiles = options.enabled_columns
            multiprocess_flag = options.multiprocess.is_enabled


        single_process_list = []
        multi_process_dict = {}
        if multiprocess_flag: # only create pool when necessary
            pool = mp.Pool(len(self._profilers))

        for col_profile_type in self._profilers:
            
            # Create profile if options allow for it or if there are no options
            if selected_col_profiles is None or \
               col_profile_type.col_type in selected_col_profiles:

                col_options = None
                if options and options.properties[col_profile_type.col_type]:
                    col_options = options.properties[col_profile_type.col_type]
                    
                self._profiles[col_profile_type.col_type] = \
                    col_profile_type(df_series.name, options=col_options)
                
                # MULTIPROCESSING
                single_process_flag = True
                if multiprocess_flag:
                    single_process_flag = False
                    try:
                        # Add update function to be applied on the pool
                        f = pool.apply_async(
                            self._profiles[col_profile_type.col_type].update,
                            (df_series,))
                        multi_process_dict[col_profile_type.col_type] = f
                    except Exception as e:
                        # Occurs when object cannot be pickled
                        single_process_flag = True

                # Add to single process list to execute later
                if single_process_flag:
                    single_process_list.append(col_profile_type.col_type)

        # Loop through remaining multiprocesses and close them out
        if multiprocess_flag:
            for col in multi_process_dict.keys():
                try:
                    f = multi_process_dict[col]
                    returned_profile = f.get()
                    if returned_profile is not None:
                        self._profiles[col] = returned_profile                
                except Exception as e:
                    # Attempt again as a single process
                    single_process_list.append(col_profile_type.col_type)

            # Close pool for new tasks  
            pool.close()
            
            # Wait for all workers to complete
            pool.join()


        # Single process thread to loop through
        for col_profile_type in single_process_list:
            try:
                self._profiles[col_profile_type].update(df_series)
            except Exception as e:
                import warnings
                warning_msg = "\n\n!!! WARNING Partial Profiler Failure !!!\n\n"
                warning_msg += "Profiling Type: {}".format(col_profile_type)
                warning_msg += "\nException: {}".format(type(e).__name__)
                warning_msg += "\nMessage: {}".format(e)

                # This is considered a major error
                if type(e).__name__ == "ValueError":
                    raise ValueError(e)
            
                warning_msg += "\n\nFor labeler errors, try installing "
                warning_msg += "the extra ml requirements via:\n\n"
                warning_msg += "$ pip install dataprofiler[ml] --user\n\n"
                
                warnings.warn(warning_msg, RuntimeWarning, stacklevel=2)

    def __add__(self, other):
        """
        Merges two profile compilers together overriding the `+` operator.

        :param other: profile compiler being add to this one.
        :type other: BaseColumnProfileCompiler
        :return: merger of the two column profilers
        """
        if type(other) is not type(self):
            raise TypeError('`{}` and `{}` are not of the same profile compiler'
                            ' type.'.format(type(self).__name__,
                                            type(other).__name__))
        elif self.name != other.name:
            raise ValueError('Column profile names are unmatched: {} != {}'
                             .format(self.name, other.name))
        elif set(self._profiles) != set(other._profiles):  # options check
            raise ValueError('Column profilers were not setup with the same '
                             'options, hence they do not calculate the same '
                             'profiles and cannot be added together.')
        merged_profile_compiler = self.__class__(pd.Series([]))
        merged_profile_compiler.name = self.name
        for profile_name in self._profiles:
            merged_profile_compiler._profiles[profile_name] = (
                self._profiles[profile_name] + other._profiles[profile_name]
            )
        return merged_profile_compiler

    def update_profile(self, df_series):
        """
        Initializes the profiles the column dataframe.
        
        :param df_series: a given column
        :type df_series: pandas.core.series.Series
        :return: None
        :rtype: None
        """
        df_series = df_series.apply(str)
        for column_profile in self._profiles:
            self._profiles[column_profile].update(df_series)            
        return self


class ColumnPrimitiveTypeProfileCompiler(BaseColumnProfileCompiler):
    
    # NOTE: these profilers are ordered. Test functionality if changed.
    _profilers = [
        DateTimeColumn,
        IntColumn,
        FloatColumn,
        TextColumn,
    ]

    @property
    def profile(self):
        profile = {
            "data_type_representation": dict(),
            "data_type": None,
            "statistics": dict()
        }
        has_found_match = False
        
        for _, profiler in self._profiles.items():

            if not has_found_match and profiler.data_type_ratio == 1.0:
                profile.update(
                    {
                        "data_type": profiler.col_type,
                        "statistics": profiler.profile,
                    }
                )
                has_found_match = True
            profile["data_type_representation"].update(
                dict([(profiler.col_type, profiler.data_type_ratio)])
            )
        return profile


class ColumnStatsProfileCompiler(BaseColumnProfileCompiler):

    # NOTE: these profilers are ordered. Test functionality if changed.
    _profilers = [
        OrderColumn,
        CategoricalColumn,
    ]

    @property
    def profile(self):
        profile = dict()
        for _, profiler in self._profiles.items():
            profile.update(profiler.profile)
        return profile


class ColumnDataLabelerCompiler(BaseColumnProfileCompiler):

    # NOTE: these profilers are ordered. Test functionality if changed.
    _profilers = [
        DataLabelerColumn
    ]

    @property
    def profile(self):
        profile = {
            "data_label": None,
            "statistics": dict()
        }
        # TODO: Only works for last profiler. Abstracted for now.
        for _, profiler in self._profiles.items():
            profile["data_label"] = profiler.data_label
            profile["statistics"].update(profiler.profile)
        return profile
