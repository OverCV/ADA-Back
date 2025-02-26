from abc import ABC, abstractmethod
from fastapi import HTTPException
import numpy as np
import networkx as nx
from api.models.props.sia import SiaType
from api.models.structure import Structure
from constants.structure import VOID
from utils.consts import ACTUAL, DIST, EFFECT, INFTY_POS, INT_ZERO, SUB_DIST, NET_ID, MIP, SMALL_PHI
from numpy.typing import NDArray

from icecream import ic

from utils.funcs import get_labels


class Sia(ABC):
    """Class Sia is used as parent class to use it's props in the used strategies."""

    def __init__(self, structure, effect, actual, distribution, dual) -> None:
        self._structure: Structure = structure
        self._effect: list[int] = effect
        self._actual: list[int] = actual
        self._target_dist: NDArray[np.float64] = distribution
        self._dual: bool = dual

        self.integrated_info: float = None
        self.min_info_part: tuple[tuple[tuple[str], tuple[str]]] = None
        self.sub_distrib: NDArray[np.float64] = None
        # ! Eliminar la id de red [#12] ! #
        self.network_id: nx.Graph | nx.DiGraph = None

    def analyze(self) -> None:
        # Analyze method returns a boolean that indicates if there's NOT a standard parameter solution
        # Obliga a que se deben de asignar los resultados dentro del método analyze, caso contrario se activa la excepción puesto se detecta hay un parámetro sin calcular (faltante).
        if self.analyze():
            raise HTTPException(
                status_code=500,
                detail=f'One or more of the SIA properties are not calculated: {self.integrated_info=}, {self.min_info_part=}, {self.sub_distrib=}, {self.network_id=}',
            )

    def get_reperoire(self) -> dict:
        ic(self.integrated_info, self.min_info_part, self.sub_distrib, self.network_id)

        concept: SiaType = {
            SMALL_PHI: self.integrated_info,
            MIP: self.min_info_part,
            SUB_DIST: self.sub_distrib.tolist(),
            DIST: self._target_dist.tolist(),
            NET_ID: self.network_id,
        }
        return concept

    @abstractmethod
    def analyze(self) -> SiaType:
        pass

    # def label_mip(self, partition: tuple[str, str]) -> tuple[tuple[tuple[str], tuple[str]]]:
    #     """
    #         # ! Mejorar
    #     Dar una tupla ['101', '010'] y ['A', 'B', 'C'] y regresar una tupla de tuplas de tuplas de strings
    #     """
    #     # Incrementamos uno puesto son índices de arreglo
    #     ic()
    #     ic(self._effect, self._actual)

    #     max_len = max(*self._effect, *self._actual) + 1
    #     labels = get_labels(max_len)
    #     concepts = [self._effect, self._actual]
    #     mip = [[[], []], [[], []]]

    #     # Negate b -> Reorder partitions. Negate k -> Invert fraction (concepts) #
    #     for k, (part, con) in enumerate(zip(partition, concepts)):
    #         for b, lbl_idx in zip(part, con):
    #             mip[1 - int(b)][1 - k].append(labels[lbl_idx])

    #     for con in mip[EFFECT]:
    #         if len(con) == INT_ZERO:
    #             con.append(VOID)
    #     for con in mip[ACTUAL]:
    #         if len(con) == INT_ZERO:
    #             con.append(VOID)

    #     return tuple(mip)
