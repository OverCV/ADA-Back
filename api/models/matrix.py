import math
from typing import Callable
from fastapi import HTTPException
import numpy as np
from numpy.typing import NDArray
import pandas as pd


from constants.structure import BIN_RANGE, BOOL_RANGE
from utils.consts import COLS_IDX, INT_ONE, INT_ZERO, ROWS_IDX, STR_ONE, STR_ZERO
from utils.funcs import big_endian, lil_endian
# from numba import njit

from server import conf

from icecream import ic


class Matrix:
    """Class Matrix is used to apply marginalization actions over it's array."""

    def __init__(self, array: NDArray[np.float64]) -> None:
        self.__array: NDArray[np.float64] = array
        # cout(1)
        self.__effect: list[int] = list(range(self.__array.shape[COLS_IDX]))
        # self.__causes: dict[int:int] = OrderedDict(
        #     (c, j) for j, c in enumerate(range(int(math.log2(self.__array.shape[ROWS_IDX]))))
        # )
        # self.__effect: list[int] = list(range(self.__array.shape[COLS_IDX]))
        self.__causes: list[int] = list(range(int(math.log2(self.__array.shape[ROWS_IDX]))))

    @property
    def shape(self):
        return self.__array.shape

    def margin(
        self,
        states: list[int],
        axis: int = ROWS_IDX,
        dual: bool = False,
        le: bool = conf.little_endian,
        data: bool = False,
    ) -> None | NDArray[np.float64]:
        """
        Marginalize the matrix over the given states. The states to marginalize are the states to drop if dual is disabled, else the given states are the states to preserve.

        Args:
            states (list[int]): Represents the states to marginalize if dual is disabled, these states must be a subset of the actual because are the states to drop or preserve.
            axis (int, optional): _description_. Defaults to ROWS_IDX. This determine if we're marginalizing rows (0) or columns (1).
            dual (bool, optional): The actual matrix has a set of actual, on whichever the incoming state is, is marginalized if dual is disabled, else the given states are the states to preserve. Defaults to False.
            le (bool, optional): _description_. Defaults to conf.little_endian. Indicates if the generated states are in little or big endian notation.
        """
        self.__array = self.__array.transpose() if axis == COLS_IDX else self.__array
        # We init an empty dataframe to fill it with the new values
        margin_df: pd.DataFrame = pd.DataFrame()
        dataframe = self.as_dataframe()
        margined_rows = 2 ** (
            len(self.__causes if axis == ROWS_IDX else self.__effect) - len(states)
        )
        # If we have a collapsed matrix, we just sum all the values.
        if len(states) == INT_ZERO:
            vector_sum: NDArray[np.float64] = np.sum(dataframe, axis=ROWS_IDX)
            collapsed: pd.DataFrame = pd.DataFrame(
                vector_sum.values.reshape(1, -1), columns=dataframe.columns, index=[STR_ZERO]
            )
            margin_df = collapsed
        else:
            notation: Callable = lil_endian if le else big_endian
            rows: list[str] = notation(len(states))
            zeros_df: pd.DataFrame = pd.DataFrame(
                np.zeros((len(rows), dataframe.shape[COLS_IDX])),
                columns=dataframe.columns,
                index=rows,
            )
            for row in dataframe.index:
                # for col in dataframe.columns:
                # States should be a ordered collection or the row[i] would be a disordered string (and that's a catastrophe).
                # element is the key, value is the position or index
                selected_row = ''.join(
                    [row[self.__causes.index(k)] for k in states],
                )
                """
                    STATES: abcde [0->0, 2->1, 3->2] [0:a,1:b,2:c]
                    Necesitamos usar el tamaño actual de la matriz usada, como se manja una única matriz, independiente del tamaño del arreglo, 
                    (b)b(bb)b
                    [0->0, 1->1, 2->2, 3->3, 4->4]
                    [0->0, 2->1, 3->2]
                    """
                # zeros_df.at[selected_row, col] += dataframe.at[row, col]
                zeros_df.loc[selected_row] += dataframe.loc[row].values
            margin_df = zeros_df

        margin_df /= margined_rows if axis == ROWS_IDX else INT_ONE
        if axis == COLS_IDX:
            self.__effect = states  #! Check case !#
        else:
            self.__causes = states
        self.__array = (
            margin_df.to_numpy().transpose() if axis == COLS_IDX else margin_df.to_numpy()
        )
        return self.__array if data else None

    def expand(
        self,
        states: list[int],
        # margined_matrix: NDArray[np.float64] = None,
        axis: int = ROWS_IDX,
        dual: bool = False,  # ! Maybe the duality is unnecesary in both margin and expand [#16] ! #
        le: bool = conf.little_endian,
        data: bool = False,
    ):
        """
        Se tiene el listado tras perdido el elemento como atributo, a su vez se puede tener la reconstrucción pasando los parámetros eliminados...

        """
        # prev_states = sorted(states + self.__causes if axis == ROWS_IDX else states + self.__effect)

        if axis == COLS_IDX:
            self.__array = self.__array.transpose()

        actual_matrix: pd.DataFrame = self.as_dataframe()
        notation: Callable = lil_endian if le else big_endian
        prev_states: list[str] = notation(len(states))

        #     f'states: {states}, actual_matrix (margined one)\n {actual_matrix}')

        empty_arr: np.ndarray = np.empty((len(prev_states), actual_matrix.shape[1]))
        zeros_mat: pd.DataFrame = pd.DataFrame(
            empty_arr, columns=actual_matrix.columns, index=prev_states
        )

        # Si es sólo un estado el marginalizado directamente establecer las filas de la matriz como el valor de la fila marginalizada.
        # Básicamente usar la única fila de la matriz marginalizada para llenar la matriz de ceros.
        if len(prev_states) == INT_ONE:
            for row in zeros_mat.index:
                # for col in zeros_mat.columns:
                # zeros_mat.at[row, col] = actual_matrix.at[prev_states, col]
                zeros_mat.loc[row] = actual_matrix.loc[prev_states].values
            return zeros_mat.to_numpy()

        """
        Iteramos la matriz grande, esta por cada fila formamos una clave basados en las self.causas, seleccionando la fila en dichas posiciones creamos la clave para seleccionar self.array en dicha posición y ubicarlo en la fila iterada.
        """

        # for row in matrix_zeros.index:
        #     for col in matrix_zeros.columns:
        #         sub_row: str = ''.join([row[j] for j, s in enumerate(states)])
        #         if sub_row in actual_matrix.index:
        #             matrix_zeros.at[row, col] = actual_matrix.at[sub_row, col]

        for row in zeros_mat.index:
            sub_row = ''.join(
                [row[states.index(j)] for j in self.__causes],
            )
            zeros_mat.loc[row] = actual_matrix.loc[sub_row].values
            # zeros_mat.loc[row] = actual_matrix.loc[sub_row]
            # for col in zeros_mat.columns:

        if axis == COLS_IDX:
            self.__array = zeros_mat.to_numpy().transpose()
            self.__effect = states
        else:
            self.__array = zeros_mat.to_numpy()
            self.__causes = states

        return zeros_mat.to_numpy() if data else None

    def on_state(
        self, istate: str, axis: int = ROWS_IDX, le: bool = conf.little_endian
    ) -> NDArray[np.float64]:
        """Select the serie at the given state."""
        if axis == COLS_IDX:
            self.__array = self.__array.transpose()

        row_istates = ''.join([istate[e] for e in self.__causes])
        col_istates = ''.join([istate[i] for i in self.__effect])
        concat_digits: str = row_istates if axis == ROWS_IDX else col_istates
        tpm = self.as_dataframe()
        # If the dataframe has only one row(collapsed tpm), return it
        arr = tpm.values if len(tpm.index) == 1 else tpm.loc[[concat_digits]].values

        self.__array = self.__array.transpose() if axis == COLS_IDX else self.__array
        return arr

    def at_states(
        self,
        istate: str,
        in_states: list[int],
        out_states: list[int],
        data: bool = False,
        axis: int = ROWS_IDX,
        le: bool = conf.little_endian,
    ):
        m: int = len(in_states)
        if axis == COLS_IDX:
            self.__array = self.__array.transpose()
        # Generamos la sub-cadena de estados específicos selectores
        row_istate = ''.join([istate[e] for e in out_states])
        # col_istates = ''.join([istate[i] for i in self.__effect])
        rows_notation: Callable = lil_endian if le else big_endian
        # Generamos los indices de las nuevas filas
        new_rows = rows_notation(m)
        zeros_df = pd.DataFrame(
            np.zeros((2**m, self.__array.shape[COLS_IDX])),  # (2**m, 2)
            index=new_rows,
            columns=list(BIN_RANGE),  # range(2)
        )
        tpm = self.as_dataframe()
        for row in tpm.index:
            row: int
            in_row: str = ''
            out_row: str = ''
            for i, s in enumerate(row):
                if i in in_states:
                    out_row += s
                else:
                    in_row += s
            if in_row == row_istate:
                zeros_df.loc[out_row] = tpm.loc[row].values
        if axis == COLS_IDX:
            self.__array = zeros_df.to_numpy().transpose()
            self.__effect = in_states
        else:
            self.__array = zeros_df.to_numpy()
            self.__causes = in_states

        return self.__array if data else None

    def as_dataframe(self, le: bool = conf.little_endian) -> pd.DataFrame:
        notation: Callable = lil_endian if le else big_endian
        num_row_vars: int = int(math.log2(self.__array.shape[ROWS_IDX]))
        num_col_vars: int = int(math.log2(self.__array.shape[COLS_IDX]))
        col_states: list[str] = notation(num_col_vars)
        row_states: list[str] = notation(num_row_vars)
        return pd.DataFrame(self.__array, columns=col_states, index=row_states)

    def get_arr(self):
        return self.__array.copy()

    def __str__(self):
        return f'{self.as_dataframe()}'
