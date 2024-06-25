import array
from math import dist
from typing import Callable
from fastapi import HTTPException
from numpy.typing import NDArray
import numpy as np

from api.models.matrix import Matrix
from api.models.props.system import SysProps
from utils.consts import INT_ONE, INT_ZERO, ROWS_IDX, STR_ONE, STR_ZERO

from collections import OrderedDict
from matplotlib.cbook import _OrderedSet


from utils.funcs import be_product, cout, le_product

from server import conf


class System:
    ''' Class System is used to easily manage the tensorial operations. '''

    def __init__(
        self, db_sys: dict[str, int | str],
        istate: str, tensor: list[NDArray[np.float64]]
    ) -> None:
        # ! Acá se debería poder marginalizar muy eficientemente!
        self.__title: str = db_sys.get(SysProps.TITLE, 'no title')
        self.__istate: str = istate

        # Setted parameters
        self.__effect: str = {True: list(range(len(tensor))), False: list()}
        self.__causes: str = {True: list(range(len(tensor))), False: list()}

        self.__tensor: dict[int, Matrix] = {
            idx: Matrix(arr) for idx, arr in enumerate(tensor)
        }
        self.__distribution: NDArray[np.float64] = None

        # self.__size = self.get_tensor_len()
        self.__nodes = set(range(db_sys.get(SysProps.SIZE, -1)))
        # validate.network(self)

    def subsystem(self, dual: bool = False) -> None:
        # Given the effect and causes, this function takes the primal selection for the tensor and returns the subsystem.
        subtensor = dict()
        for idx in self.__effect[not dual]:
            cout(f'idx: {idx}')
            mat: Matrix = self.__tensor[idx]
            mat.margin(self.__causes[not dual])
            subtensor[idx] = self.__tensor[idx]
        # Eliminamos los estados del lado elegido para
        self.__effect[dual] = list()
        self.__causes[dual] = list()
        # Asignamos el tensor reducido
        self.__tensor = subtensor

    def obtain_dist(self, data: bool = False) -> NDArray[np.float64] | None:
        """Calculates the serie distribution of the system. Precondition is that the system has to be set it's effect and causes correctly depending on the size of the tensor. Then, those matrices are used for the purpose of obtaining the full distribution composed by the primal and dual distributions.

        effect = {T;[0,1,4], F:[]} causes = {T: [2,4], F: []}
        effect 101 ; causes 01

        Args:
            data (bool, optional): When set to true, returns the probability distribution, by default is set as a calculated attribute. Defaults to False.

        Returns:
            NDArray[np.float64]: The probability distribution array.
            None: If the data is set to False, else returns the distribution of the system.
        """
        ''' Returns the distribution of the system. '''

        # if len(effect) != len(causes) and len(effect) != len(self.__tensor):
        #     raise HTTPException(
        #         status_code=400,
        #         detail='Effect and causes must have the same length. Also the tensor

        # Accedemos al primal y dual del sistema

        prim_effect = self.__effect[True]
        dual_effect = self.__effect[False]

        prim_tensor: list[NDArray[np.float64]]
        dual_tensor: list[NDArray[np.float64]]
        unit_matrix: NDArray[np.float64] = np.array(
            [INT_ONE], dtype=np.float64
        )
        # cout(f'1. prim {prim_effect}, dual {dual_effect}')
        # By definition, is not possible to have both tensors empty
        prim_tensor = unit_matrix if len(prim_effect) == INT_ZERO else [
            self.__tensor[idx].at_state(self.__istate)
            for idx in prim_effect
        ]
        dual_tensor = unit_matrix if len(dual_effect) == INT_ZERO else [
            self.__tensor[idx].at_state(self.__istate)
            for idx in dual_effect
        ]
        # cout(f'2. prim {prim_tensor}, dual {dual_tensor}')

        product: Callable = be_product if conf.little_endian else le_product
        prim_dist = product(prim_tensor)
        dual_dist = product(dual_tensor)

        dist = product([prim_dist, dual_dist])
        return dist if data else None

    def get_distribution(self) -> NDArray[np.float64]:
        pass

    def get_istate(self) -> str:
        return self.__istate

    def get_effect(self) -> str:
        return self.__effect

    def get_causes(self) -> str:
        return self.__causes

    def set_effect(self, effect: str) -> None:
        self.__effect[True], self.__effect[False] = list(), list()
        for i, b in enumerate(effect):
            self.__effect[bool(int(b))].append(i)

    def set_causes(self, causes: str) -> None:
        self.__causes[True], self.__causes[False] = list(), list()
        for i, b in enumerate(causes):
            self.__causes[bool(int(b))].append(i)

    def get_tensor(self) -> list[Matrix]:
        return self.__tensor

    def get_tensor_len(self) -> int:
        return len(self.__tensor)

    def __str__(self) -> str:
        return f'{self.__title} : {self.__istate}, {self.__effect}, {self.__causes}, {self.__nodes}'
