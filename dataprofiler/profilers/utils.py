
import os
import collections
import random
import math
import warnings
import numpy as np


def dict_merge(dct, merge_dct):
    # Recursive dictionary merge
    # Copyright (C) 2016 Paul Durivage <pauldurivage+github@gmail.com>
    # 
    # This program is free software: you can redistribute it and/or modify
    # it under the terms of the GNU General Public License as published by
    # the Free Software Foundation, either version 3 of the License, or
    # (at your option) any later version.
    # 
    # This program is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    # GNU General Public License for more details.
    # 
    # You should have received a copy of the GNU General Public License
    # along with this program.  If not, see <https://www.gnu.org/licenses/>.
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.abc.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


class KeyDict(collections.defaultdict):
    """
    Helper class for sample_in_chunks. Allows keys that are missing to become
    the values for that key.
    From:
    https://www.drmaciver.com/2018/01/lazy-fisher-yates-shuffling-for-precise-rejection-sampling/
    """
    def __missing__(self, key):
        return key


def shuffle_in_chunks(data_length, chunk_size):
    """
    A generator for creating shuffled indexes in chunks. This reduces the cost
    of having to create all indexes, but only of that what is needed.
    Initial Code idea from:
    https://www.drmaciver.com/2018/01/lazy-fisher-yates-shuffling-for-precise-rejection-sampling/
    
    :param data_length: length of data to be shuffled
    :param chunk_size: size of shuffled chunks
    :return: list of shuffled indices of chunk size
    """

    if not data_length or data_length == 0 \
       or not chunk_size or chunk_size == 0:
        return []
    
    rng = np.random.default_rng()
    if 'DATAPROFILER_SEED' in os.environ:
        try:
            seed_value = int(os.environ.get('DATAPROFILER_SEED'))
            rng = np.random.default_rng(seed_value)
        except ValueError as e:
            warnings.warn("Seed should be an integer", RuntimeWarning)


    indices = KeyDict()
    j = 0
    
    # loop through all chunks
    for chunk_ind in range(max(math.ceil(data_length / chunk_size), 1)):

        # determine the chunk size and preallocate an array
        true_chunk_size = min(chunk_size, data_length - chunk_size * chunk_ind)
        values = [-1] * true_chunk_size

        
        # Generate random list of indicies         
        lower_bound_list = np.array(range(j, j + true_chunk_size))
        random_list = rng.integers(lower_bound_list, data_length)


        # shuffle the indexes
        for count in range(true_chunk_size):

            # get a random index to swap and swap it with j
            k = random_list[count]
            indices[j], indices[k] = indices[k], indices[j]

            # set the swapped value to the output
            values[count] = indices[j]

            # increment so as not to include values already swapped
            j += 1
            
        yield values


def warn_on_profile(col_profile, e):
    """
    Returns a warning if a given profile errors (tensorflow typcially)

    :param col_profile: Name of the column profile
    :type col_profile: str
    :param e: Error message from profiler error
    :type e: Exception
    """
    import warnings
    warning_msg = "\n\n!!! WARNING Partial Profiler Failure !!!\n\n"
    warning_msg += "Profiling Type: {}".format(col_profile)
    warning_msg += "\nException: {}".format(type(e).__name__)
    warning_msg += "\nMessage: {}".format(e)
    # This is considered a major error 
    if type(e).__name__ == "ValueError": raise ValueError(e)
    warning_msg += "\n\nFor labeler errors, try installing "
    warning_msg += "the extra ml requirements via:\n\n"
    warning_msg += "$ pip install dataprofiler[ml] --user\n\n"
    warnings.warn(warning_msg, RuntimeWarning, stacklevel=2)


def partition(data, chunk_size):
    """
    Creates a generator which returns the data
    in the specified chunk size.
    
    :param data: list, dataframe, etc
    :type data: list, dataframe, etc
    :param chunk_size: size of partition to return
    :type chunk_size: int
    """
    for idx in range(0, len(data), chunk_size):
        yield data[idx:idx+chunk_size]

