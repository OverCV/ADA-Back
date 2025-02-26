from typing import OrderedDict
import numpy as np
from numpy.typing import NDArray
import pyphi.labels
import pyphi.partition
import pyphi.tpm

from api.models.props.sia import SiaType

from api.models.structure import Structure
from api.schemas.structure import StructureResponse


from api.services.analyze.strats.branch import Branch
from api.services.analyze.strats.genetic import Genetic
from api.services.analyze.strats.force import BruteForce

import pyphi
import pyphi.compute
from pyphi.models.cuts import Bipartition, Part
from pyphi.labels import NodeLabels


import copy
from api.services.analyze.strats.frank_mech import FMAlgorithm
from api.services.analyze.strats.QREdges import QREdges
from constants.structure import BOOL_RANGE, DIST, VOID
from utils.consts import (
    COLS_IDX,
    MIP,
    NET_ID,
    SMALL_PHI,
    STR_ONE,
    SUB_DIST,
)

from icecream import ic

from utils.funcs import get_labels, lil_endian_int


# pyphi.config.load_file('pyphi_config_3.0.yml')
pyphi.config.PARALLEL_CONCEPT_EVALUATION = False
pyphi.config.PARALLEL_CUT_EVALUATION = False
pyphi.config.PARALLEL_COMPLEX_EVALUATION = False


"""Class Compute is used to compute all different System Irreducibility analysis."""


class Compute:
    def __init__(
        self,
        struct: StructureResponse,
        istate: str,
        str_effect: str,
        str_actual: str,
        str_bgcond: str,
        subtensor: NDArray[np.float64],
        dual: bool = False,
    ) -> None:
        # Siempre preservamos la superestructura
        self.__sup_struct: Structure = Structure(
            db_struct=struct.model_dump(),
            istate=istate,
            tensor=subtensor,
        )
        self.__str_effect: str = str_effect
        self.__str_actual: str = str_actual
        self.__str_bgcond: str = str_bgcond
        self.__dual: bool = dual

        self.__struct: Structure = None
        self.__effect: dict[bool, list[int]] = {bin: [] for bin in BOOL_RANGE}
        self.__actual: dict[bool, list[int]] = {bin: [] for bin in BOOL_RANGE}
        self.__bgcond: dict[bool, list[int]] = {bin: [] for bin in BOOL_RANGE}
        self.__distribution: NDArray[np.float64] = None

    def init_concept(self) -> bool:
        """
        Desde este nivel se deifinen las condiciones de bg, las cuales permiten conocer los elementos/ínidces usables para los diferentes subsistemas a generar.
        """

        bgcond_elems = [
            idx for idx, bg in enumerate(self.__str_bgcond) if (bg == STR_ONE) == (not self.__dual)
        ]
        for i, e in enumerate(self.__str_effect):
            if i in bgcond_elems:
                self.__effect[e == STR_ONE].append(i)
        for j, c in enumerate(self.__str_actual):
            if j in bgcond_elems:
                self.__actual[c == STR_ONE].append(j)
        for i, bg in enumerate(self.__str_bgcond):
            self.__bgcond[bg == STR_ONE].append(i)

        # Preservamos la superestructura para trabajar con una nueva
        self.__struct: Structure = copy.deepcopy(self.__sup_struct)
        self.__struct.set_bg_cond(self.__bgcond)
        self.__struct.create_distrib(self.__effect, self.__actual)
        self.__distribution = self.__struct.get_distrib(self.__dual)

        return self.__distribution is not None

    def use_pyphi(self) -> SiaType:
        # Selección de nodos mediante pyphi
        bg_set = set(
            idx for idx, bg in enumerate(self.__str_bgcond) if (bg == STR_ONE) == (not self.__dual)
        )

        tensor: OrderedDict = self.__sup_struct.get_tensor()
        tpms = np.array([mat.get_arr()[:, COLS_IDX] for mat in tensor.values()])
        tpm_state_node: NDArray[np.float64] = np.column_stack(tpms)

        num_nodes: int = self.__sup_struct.get_tensor_len()
        istate = tuple(int(i) for i in self.__sup_struct.get_istate())

        str_labels = get_labels(num_nodes)
        idx_labels = tuple(range(num_nodes))
        labels = NodeLabels(str_labels, idx_labels)

        network = pyphi.Network(tpm=tpm_state_node, node_labels=labels)

        # Aplicar las condiciones de background
        # bg_istate = tuple(
        #     istate[i]
        #     for i, bg in enumerate(self.__str_bgcond)
        #     if (bg == STR_ONE) == (not self.__dual)
        # )

        bg_labels: tuple[str] = tuple(
            labels[i]
            for i, bg in enumerate(self.__str_bgcond)
            if (bg == STR_ONE) == (not self.__dual)
        )

        # ic(bg_istate, bg_labels)

        sub_system = pyphi.Subsystem(
            network=network,
            state=istate,
            nodes=bg_labels,
        )

        mech_idx = tuple(
            i
            for i, x in enumerate(self.__str_actual)
            if all([(x == STR_ONE) == (not self.__dual), i in bg_set])
        )

        purv_idx = tuple(
            i
            for i, x in enumerate(self.__str_effect)
            if all([(x == STR_ONE) == (not self.__dual), i in bg_set])
        )

        ic(mech_idx, purv_idx)

        er = sub_system.effect_mip(mech_idx, purv_idx)
        ic(er)

        # ? Reconstrucción de resultados

        integrated_info: float = er.phi

        repertoire = er.repertoire
        repertoire = repertoire.squeeze()

        part_reper = er.partitioned_repertoire
        part_reper = part_reper.squeeze()

        sub_states: list[tuple[int, ...]] = copy.copy(list(lil_endian_int(repertoire.ndim)))

        distribution: list[float] = [repertoire[sub_state] for sub_state in sub_states]
        part_distrib: list[float] = [part_reper[sub_state] for sub_state in sub_states]

        min_info_part: Bipartition = er.partition

        dual: Part = min_info_part.parts[not self.__dual]
        prim: Part = min_info_part.parts[self.__dual]
        dual_mech, dual_purv = dual.mechanism, dual.purview
        prim_mech, prim_purv = prim.mechanism, prim.purview

        # ic(bg_labels)
        # ic(dual_purv, dual_mech, prim_purv, prim_mech)

        min_info_part = [
            [
                [labels[i] for i in prim_mech] if prim_mech else [VOID],
                [labels[i] for i in prim_purv] if prim_purv else [VOID],
            ],
            [
                [labels[i] for i in dual_mech] if dual_mech else [VOID],
                [labels[i] for i in dual_purv] if dual_purv else [VOID],
            ],
        ]

        return {
            SMALL_PHI: integrated_info,
            MIP: min_info_part,
            DIST: distribution,
            SUB_DIST: part_distrib,
            # ! Debería la conf permitir asignar o no el índice del grafo, BAJAR NIVEL [#18] ! #
            # NET_ID: network_id if conf.store_network else net_id,
        }

    def use_brute_force(self) -> SiaType:
        sia_force: BruteForce = BruteForce(
            self.__struct,
            self.__effect[not self.__dual],
            self.__actual[not self.__dual],
            self.__distribution,
            self.__dual,
        )
        sia_force.analyze()
        return sia_force.get_reperoire()

    def use_min_frank_mech(self) -> bool:
        sia_mst: FMAlgorithm = FMAlgorithm(
            self.__struct,
            self.__effect[not self.__dual],
            self.__actual[not self.__dual],
            self.__distribution,
            self.__dual,
        )
        sia_mst.analyze()
        return sia_mst.get_reperoire()

    def use_branch_and_bound(self) -> bool:
        sia_branch: Branch = Branch(
            self.__struct,
            self.__effect[not self.__dual],
            self.__actual[not self.__dual],
            self.__distribution,
            self.__dual,
        )
        sia_branch.analyze()
        return sia_branch.get_reperoire()

    def use_queyranne(self) -> bool:
        sia_queyranne: QREdges = QREdges(
            self.__struct,
            self.__effect[not self.__dual],
            self.__actual[not self.__dual],
            self.__distribution,
            self.__dual,
        )
        sia_queyranne.analyze()
        return sia_queyranne.get_reperoire()

    def use_genetic_algorithm(self, ctrl_params: list[dict[str, int | float]]) -> bool:
        # ! Made for S2P
        sia_genetic: Genetic = Genetic(
            self.__struct,
            self.__effect[not self.__dual],
            self.__actual[not self.__dual],
            self.__distribution,
            self.__dual,
            ctrl_params,
        )
        sia_genetic.analyze()
        return sia_genetic.get_reperoire()
        # ! Dada una cadena de binarios y una lista de elementos, las combinaciones binarias de elementos determinan si el elemento se va al True o al False de los canales del efecto o causa que se maneje

        # if not sv.has_valid_istate(system.istate, len(subtensor)):
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail=f'Invalid initial state: State {
        #             system.istate} needs to be size {len(subtensor)}.'
        #     )

    def use_dynamic_programming(self) -> bool:
        pass

    def use_game_theory(self) -> bool:
        pass

    def use_evolutionary_algorithm(self) -> bool:
        pass

    def use_differential_evolution(self) -> bool:
        pass

    def use_simulated_annealing(self) -> bool:
        pass

    def use_tabu_search(self) -> bool:
        pass

    def use_stochastic_programming(self) -> bool:
        pass

    def use_ant_colony(self) -> bool:
        pass

    def use_swarm_intelligence(self) -> bool:
        pass

    def use_neural_network(self) -> bool:
        pass

    def use_deep_learning(self) -> bool:
        pass

    def use_markov_decision_process(self) -> bool:
        pass

    def use_hidden_markov_model(self) -> bool:
        pass

    def use_reinforcement_learning(self) -> bool:
        pass

    def use_linear_programming(self) -> bool:
        pass

    def use_integer_programming(self) -> bool:
        pass

    def use_convex_optimization(self) -> bool:
        pass

    def use_nonlinear_programming(self) -> bool:
        pass

    def use_quadratic_programming(self) -> bool:
        pass

    def use_semi_definite_programming(self) -> bool:
        pass

    def use_boolean_programming(self) -> bool:
        pass

    def use_fuzzy_programming(self) -> bool:
        pass

    def use_quantum_neural_network(self) -> bool:
        pass

    def use_wave_function_collapse(self) -> bool:
        pass

    def use_backpropagation(self) -> bool:
        pass

    def use_convolutional_neural_network(self) -> bool:
        pass

    def use_q_learning(self) -> bool:
        pass

    def use_deep_q_learning(self) -> bool:
        pass

    def use_policy_gradient(self) -> bool:
        pass

    def use_actor_critic(self) -> bool:
        pass

    def use_multi_objective_programming(self) -> bool:
        pass

    def use_decision_theory(self) -> bool:
        pass

    def use_markov_chain(self) -> bool:
        pass

    def use_markov_random_field(self) -> bool:
        pass

    def use_bayesian_network(self) -> bool:
        pass

    def use_belief_propagation(self) -> bool:
        pass

    """  """

    def use_gibbs_sampling(self) -> bool:
        pass

    def use_variational_inference(self) -> bool:
        pass

    def use_expectation_maximization(self) -> bool:
        pass

    def use_kalman_filter(self) -> bool:
        pass

    def use_particle_filter(self) -> bool:
        pass

    def use_ensemble_filter(self) -> bool:
        pass

    def use_extended_kalman_filter(self) -> bool:
        pass

    def use_unscented_kalman_filter(self) -> bool:
        pass

    def use_information_filter(self) -> bool:
        pass

    def use_smoothed_particle_filter(self) -> bool:
        pass

    def use_rao_blackwellized_particle_filter(self) -> bool:
        pass

    def use_gaussian_filter(self) -> bool:
        pass

    def use_extended_information_filter(self) -> bool:
        pass

    def use_unscented_information_filter(self) -> bool:
        pass

    def use_extended_gaussian_filter(self) -> bool:
        pass

    def use_unscented_gaussian_filter(self) -> bool:
        pass

    def use_finite_state_machine(self) -> bool:
        pass

    def use_turing_machine(self) -> bool:
        pass

    def use_neural_turing_machine(self) -> bool:
        pass

    def use_recurrent_neural_network(self) -> bool:
        pass

    def use_long_short_term_memory(self) -> bool:
        pass

    def use_gated_recurrent_unit(self) -> bool:
        pass

    def use_bidirectional_recurrent_neural_network(self) -> bool:
        pass

    def use_deep_belief_network(self) -> bool:
        pass

    def use_restricted_boltzmann_machine(self) -> bool:
        pass

    def use_autoencoder(self) -> bool:
        pass

    def use_multi_layer_perceptron(self) -> bool:
        pass

    def use_radial_basis_function_network(self) -> bool:
        pass

    def use_optical_neural_network(self) -> bool:
        pass

    def use_pulsed_neural_network(self) -> bool:
        pass

    def use_spiking_neural_network(self) -> bool:
        pass

    def use_neuromorphic_engineering(self) -> bool:
        pass

    def use_neural_network_quantum_state(self) -> bool:
        pass

    def use_hopfield_network(self) -> bool:
        pass

    def use_associative_memory(self) -> bool:
        pass

    def use_widrow_hoff_rule(self) -> bool:
        pass

    def use_resilient_backpropagation(self) -> bool:
        pass

    def use_quickprop(self) -> bool:
        pass

    def use_contrastive_divergence(self) -> bool:
        pass

    def use_stochastic_gradient_descent(self) -> bool:
        pass

    def use_batch_gradient_descent(self) -> bool:
        pass

    def use_yarowsky_algorithm(self) -> bool:
        pass

    def use_zhang_shasha_algorithm(self) -> bool:
        pass

    def use_hungarian_algorithm(self) -> bool:
        pass
