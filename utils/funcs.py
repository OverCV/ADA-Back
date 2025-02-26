from functools import cache, reduce, wraps
import itertools as it
import math
import time
from typing import Callable

from pyemd import emd

from numpy.typing import NDArray
from decimal import Decimal, getcontext
import numpy as np
import pandas as pd
# from scipy.stats import wasserstein_distance


from constants.format import HAMMING_DIST
from constants.structure import VOID
from utils.consts import ACTUAL, BASE_2, EFFECT, FLOAT_ZERO, INT_ONE, INT_ZERO, ROWS_IDX, STR_ONE

from server import conf
# from icecream import ic

# Set the precision to 50 decimal places
getcontext().prec = 50

""" If needed, this class could partitionate into several modules associated with the business logic. """

up_sep_ln: str = '\n' + '︵' * 16 + '\n'
dn_sep_ln: str = '\n' + '︶' * 16 + '\n'
up_sep: str = '︵' * 16
dn_sep: str = '︶' * 16


def emd_fn(
    u: NDArray[np.float64],
    v: NDArray[np.float64],
    le: bool = conf.little_endian,
    md: str = conf.metric_distance,
) -> float:
    """Returns the Earth Mover's Distance between two distributions."""
    # return wasserstein_distance(u, v)
    u: NDArray[np.float64] = np.asarray(u, dtype=np.float64).flatten()
    v: NDArray[np.float64] = np.asarray(v, dtype=np.float64).flatten()

    if len(u) != len(v):
        raise ValueError('Both distributions must have the same size')

    max_len: int = int(math.log2(len(u)))
    endian_keys: list[str] = lil_endian(max_len) if le else big_endian(max_len)
    earth_moved: float = FLOAT_ZERO

    while not np.allclose(u, INT_ZERO):
        u_sorter: NDArray[np.intp] = np.argsort(-u)
        v_sorter: NDArray[np.intp] = np.argsort(-v)

        u_idx: int = u_sorter[ROWS_IDX]
        v_idx: int = v_sorter[ROWS_IDX]

        end_u_key: int = int(endian_keys[u_idx], BASE_2)
        end_v_key: int = int(endian_keys[v_idx], BASE_2)

        remainder: float = min(u[u_idx], v[v_idx])
        u[u_idx] -= remainder
        v[v_idx] -= remainder

        valid_metrics: dict[str, Callable] = {
            HAMMING_DIST: hamming_distance,
        }
        metric_distance: Callable[[int, int], int] = valid_metrics[md]

        distance: int = metric_distance(end_u_key, end_v_key)
        earth_moved += remainder * distance
    return earth_moved


@cache
def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def emd_pyphi(u: NDArray[np.float64], v: NDArray[np.float64]) -> float:
    """
    Calculate the Earth Mover's Distance (EMD) between two probability distributions u and v.
    The Hamming distance was used as the ground metric.
    """
    if not all(isinstance(arr, np.ndarray) for arr in [u, v]):
        raise TypeError('u and v must be numpy arrays.')

    n: int = len(u)
    costs: NDArray[np.float64] = np.empty((n, n))

    for i in range(n):
        # Utiliza comprensión de listas para calcular los costos
        costs[i, :i] = [hamming_distance(i, j) for j in range(i)]
        costs[:i, i] = costs[i, :i]  # Reflejar los valores
    np.fill_diagonal(costs, 0)

    cost_mat: NDArray[np.float64] = np.array(costs, dtype=np.float64)
    return emd(u, v, cost_mat)


@cache
def lil_endian(n: int) -> list[str]:
    """Generate a list of strings representing the numbers in
    little-endian for indices in ``range(2**n)``.
    """
    return [bin(i)[2:].zfill(n)[::-1] for i in range(2**n)]


@cache
def big_endian(n: int) -> list[str]:
    """Generate a list of strings representing the numbers in
    big-endian for indices in ``range(2**n)``.
    """
    return [bin(i)[2:].zfill(n) for i in range(2**n)]


def product(
    arrays: list[tuple[tuple[int, ...], NDArray[np.float64]]], le: bool = conf.little_endian
) -> tuple[tuple[int, ...], NDArray[np.float64]]:
    # return reduce(lambda x, y: np.kron
    return (
        arrays[0]
        if len(arrays) == 1
        else reduce(
            lambda x, y: bin_prod(x, y, le),
            arrays,
        )
    )


def bin_prod(
    idx_dist_u: tuple[tuple[int, ...], np.ndarray],
    idx_dist_v: tuple[tuple[int, ...], np.ndarray],
    le: bool,
) -> tuple[tuple[int, ...], np.ndarray]:
    """Returns the binary product of two arrays."""
    u_idx, u = idx_dist_u
    v_idx, v = idx_dist_v
    u = u.flatten()
    v = v.flatten()
    d_len = len(u_idx) + len(v_idx)
    result = np.zeros(2**d_len, dtype=np.float64)
    endian_keys = lil_endian(d_len) if le else big_endian(d_len)
    df_result = pd.DataFrame([result], columns=endian_keys)
    combined_idx = tuple(sorted(set(u_idx) | set(v_idx)))
    for key in endian_keys:
        u_key = ''.join(key[combined_idx.index(i)] for i in u_idx)
        v_key = ''.join(key[combined_idx.index(i)] for i in v_idx)
        u_val = u[int(u_key[::-1], 2)]
        v_val = v[int(v_key[::-1], 2)]
        df_result.at[ROWS_IDX, key] = u_val * v_val
    return combined_idx, df_result.values


def be_prod(arrays: list[NDArray[np.float64]]) -> NDArray[np.float64]:
    """Returns the tensor product of a list of arrays."""
    return reduce(lambda x, y: np.kron(x, y), arrays)


def le_prod(arrays: list[NDArray[np.float64]]) -> NDArray:
    """Returns the tensor product of a list of arrays."""
    return reduce(lambda x, y: np.kron(y, x), arrays)


@cache
def all_states(n, lil_endian=conf.little_endian):
    """Return all binary states until N.

    Args:
        n (int): The number of elements in the system.
        big_endian (bool): Whether to return the states in big-endian order
            instead of little-endian order.

    Yields:
        tuple[int]: The next state of an ``n``-element system, in little-endian
        order unless ``big_endian`` is ``True``.
    """
    if n == 0:
        return

    for state in it.product((INT_ZERO, INT_ONE), repeat=n):
        yield state if lil_endian else state[::-1]


# @cache
def lil_endian_int(n: int):
    """Generate a list of integers representing the numbers in
    little-endian for indices in ``range(2**n)``.
    """
    # return [int(bin(i)[2:].zfill(n)[::-1], BASE_2) for i in range(2**n)]
    for state in it.product((0, 1), repeat=n):
        yield state[::-1]


@cache
def big_endian_int(n: int) -> list[int]:
    """Generate a list of integers representing the numbers in
    big-endian for indices in ``range(2**n)``.
    """
    return [int(bin(i)[2:].zfill(n), BASE_2) for i in range(2**n)]


@cache
def get_labels(n: int) -> tuple[str, ...]:
    def get_excel_column(n: int) -> str:
        if n <= 0:
            return ''
        return get_excel_column((n - 1) // 26) + chr((n - 1) % 26 + ord('A'))

    return tuple([get_excel_column(i) for i in range(1, n + 1)])


def dec2bin(number: int, digits: int) -> str:
    return f'{number:0{digits}b}'


async def logger(func):
    def wrapper(*args, **kwargs):
        print('\n')
        result = func(*args, **kwargs)
        print('\n')
        return result

    return wrapper


# def printnl(*args):
#     print()
#     for arg in args:
#         print(arg)
#     # '\n'
#     print()


def cout(*args):
    print(up_sep_ln)
    for arg in args:
        print(arg)
    print(dn_sep_ln)


def coute(*args):
    print(up_sep)
    for arg in args:
        print(arg)
    print(dn_sep)


def combs(a, r):
    """NumPy implementation of ``itertools.combinations``.

    Return successive ``r``-length combinations of elements in the array ``a``.

    Args:
        a (np.ndarray): The array from which to get combinations.
        r (int): The length of the combinations.

    Returns:
        np.ndarray: An array of combinations.
    """
    # Special-case for 0-length combinations
    if r == 0:
        return np.asarray([])

    a = np.asarray(a)
    data_type = a.dtype if r == 0 else np.dtype([('', a.dtype)] * r)
    b = np.fromiter(it.combinations(a, r), data_type)
    return b.view(a.dtype).reshape(-1, r)


def timer(func: Callable):
    def wrapper(*args, **kwargs):
        t_start = time.time()
        result = func(*args, **kwargs)
        t_total = time.time()
        print(f'{func.__name__} took {t_total - t_start} seconds')
        return result

    return wrapper


# def memoize(func):
#     # Store the results in a dictionary that maps arguments to results
#     cache = {}

#     # Define the wrapper function to return.
#     def wrapper(*args, **kwargs):
#         # If these arguments haven't been seen before;
#         if (args, kwargs) not in cache:
#             # Call cache and store the result
#             cache[(args, kwargs)] = func(*args, **kwargs)
#         return cache[(args, kwargs)]

#     return wrapper


def temporizer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()  # Iniciar temporizador
        result = await func(*args, **kwargs)  # Llamar a la función original
        end_time = time.time()  # Detener temporizador

        # Calcular el tiempo de ejecución
        delay = end_time - start_time

        # Almacenar el tiempo en el diccionario
        conf.execution_times[func.__name__] = delay

        return result  # Retornar el resultado de la función original

    return wrapper


def label_mip(
    partition: tuple[str, str], concept: tuple[tuple[int, ...], tuple[int, ...]]
) -> tuple[tuple[tuple[str], tuple[str]], tuple[tuple[str], tuple[str]]]:
    """
        # ! Mejorar
    Dar una tupla ['101', '010'] y ['A', 'B', 'C'] y regresar una tupla de tuplas de tuplas de strings
    """
    effect, actual = concept
    # Incrementamos uno puesto son índices de arreglo
    max_len = max(*effect, *actual) + 1
    labels = get_labels(max_len)
    concepts = [effect, actual]
    mip = [[[], []], [[], []]]

    # Negate b -> Reorder partitions. Negate k -> Invert fraction (concepts) #
    for k, (part, con) in enumerate(zip(partition, concepts)):
        for b, lbl_idx in zip(part, con):
            mip[1 - int(b)][1 - k].append(labels[lbl_idx])

    for con in mip[EFFECT]:
        if len(con) == INT_ZERO:
            con.append(VOID)
    for con in mip[ACTUAL]:
        if len(con) == INT_ZERO:
            con.append(VOID)

    return tuple(mip)
