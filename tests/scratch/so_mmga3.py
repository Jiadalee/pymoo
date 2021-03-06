import matplotlib.pyplot as plt
import numpy as np
from pyrecorder.recorders.file import File
from pyrecorder.video import Video

from pymoo.algorithms.genetic_algorithm import GeneticAlgorithm
from pymoo.algorithms.so_genetic_algorithm import GA
from pymoo.docs import parse_doc_string
from pymoo.model.mating import Mating
from pymoo.model.population import Population
from pymoo.model.survival import Survival
from pymoo.operators.crossover.simulated_binary_crossover import SimulatedBinaryCrossover
from pymoo.operators.mutation.polynomial_mutation import PolynomialMutation
from pymoo.operators.sampling.random_sampling import FloatRandomSampling
from pymoo.operators.selection.random_selection import RandomSelection
from pymoo.operators.selection.tournament_selection import TournamentSelection, compare
from pymoo.optimize import minimize
from pymoo.problems.single.multimodal import MultiModalSimple1, curve, MultiModalSimple2
from pymoo.util.display import SingleObjectiveDisplay
from pymoo.util.misc import vectorized_cdist
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
from pymoo.util.termination.default import SingleObjectiveDefaultTermination
from pymoo.visualization.scatter import Scatter


# =========================================================================================================
# Implementation
# =========================================================================================================


def comp_by_rank(pop, P, **kwargs):
    S = np.full(P.shape[0], np.nan)

    for i in range(P.shape[0]):
        a, b = P[i, 0], P[i, 1]
        S[i] = compare(a, pop[a].get("rank"), b, pop[b].get("rank"), method='smaller_is_better',
                       return_random_if_equal=True)

    return S[:, None].astype(np.int)


class MMGA(GeneticAlgorithm):

    def __init__(self,
                 pop_size=100,
                 sampling=FloatRandomSampling(),
                 selection=RandomSelection(),
                 crossover=SimulatedBinaryCrossover(prob=0.9, eta=3),
                 mutation=PolynomialMutation(prob=None, eta=5),
                 eliminate_duplicates=True,
                 n_offsprings=None,
                 display=SingleObjectiveDisplay(),
                 **kwargs):
        """

        Parameters
        ----------
        pop_size : {pop_size}
        sampling : {sampling}
        selection : {selection}
        crossover : {crossover}
        mutation : {mutation}
        eliminate_duplicates : {eliminate_duplicates}
        n_offsprings : {n_offsprings}

        """

        super().__init__(pop_size=pop_size,
                         sampling=sampling,
                         selection=selection,
                         crossover=crossover,
                         mutation=mutation,
                         survival=NichingSurvival(),
                         eliminate_duplicates=eliminate_duplicates,
                         n_offsprings=n_offsprings,
                         display=display,
                         **kwargs)

        # self.mating = NeighborBiasedMating(selection,
        #                                    crossover,
        #                                    mutation,
        #                                    repair=self.mating.repair,
        #                                    eliminate_duplicates=self.mating.eliminate_duplicates,
        #                                    n_max_iterations=self.mating.n_max_iterations)

        self.default_termination = SingleObjectiveDefaultTermination()


class NichingSurvival(Survival):

    def __init__(self) -> None:
        super().__init__(True)

    def _do(self, problem, pop, n_survive, out=None, algorithm=None, **kwargs):
        X, F = pop.get("X", "F")
        if F.shape[1] != 1:
            raise ValueError("FitnessSurvival can only used for single objective single!")

        # the final indices of surviving individuals
        survivors = []

        # calculate the normalized distance
        D = vectorized_cdist(X, X)
        # np.fill_diagonal(D, np.inf)
        norm = np.linalg.norm(problem.xu - problem.xl)
        D /= norm

        # find the best solution in the population
        S = np.argmin(F[:, 0])

        # create the data structure to work with in order to flag survivors
        survivors = []
        remaining = [k for k in range(len(pop)) if k != S]

        while len(survivors) < n_survive:

            # the extreme point for decision making
            farthest = D[S, :].argmax()

            # sort by distance to best
            delta_x = D[S, :] / D[S, farthest]
            delta_f = (F[:, 0] - F[S, 0]) / (F[farthest, 0] - F[S, 0])
            f = np.column_stack([-delta_x, delta_f])
            z = np.array([-1, 0])
            p = 2

            val = ((f - z) ** p).sum(axis=1) ** (1 / p)
            survivors = val.argsort()[:n_survive]
            pop[survivors].set("v", val[survivors])



            plt.figure(figsize=(5, 5))
            plt.scatter(X, F, color="black", alpha=0.8, s=20, label='pop')
            plt.scatter(X[survivors], F[survivors], color="red", label="survivors")
            v = np.round(pop[survivors].get("v"), 3)

            for i in range(len(survivors)):
                x = X[survivors][i]
                y = F[survivors][i]
                plt.text(x, y, v[i], fontsize=9)



            plt.scatter(X[farthest], F[farthest], color="green", label="survivors")

            _curve = curve(problem)
            plt.plot(_curve[:, 0], _curve[:, 1], color="black")
            plt.xlabel("X")
            plt.ylabel("F")
            plt.legend()
            plt.show()

            return pop[survivors]

            survivors.append(remaining[val.argmin()])
            remaining = [k for k in range(len(pop)) if k != S]

            plt.scatter(X, F)
            plt.scatter(X[survivors], F[survivors], color="red", marker='x')

            _curve = curve(problem)
            plt.plot(_curve[:, 0], _curve[:, 1], color="black")
            plt.xlabel("X")
            plt.ylabel("F")
            plt.show()

        return pop[fronts[0]]

        plt.scatter(delta_x, delta_f)
        plt.scatter(delta_x[nds], delta_f[nds], color="red")
        plt.xlabel("D")
        plt.ylabel("F")
        plt.show()

        pop[S].set("rank", 0)

        # initialize utility data structures
        survivors = [S]
        remaining = [k for k in range(len(pop)) if k != S]

        n_neighbors = 10
        cnt = 1

        while len(survivors) < n_survive:

            closest = D[survivors, :][:, remaining].argmin(axis=0)

            delta_f = F[remaining, 0] - F[np.argmin(F[:, 0]), 0]
            delta_x = D[closest, remaining]
            fitness = delta_f / delta_x

            S = remaining[np.argmin(fitness)]

            if algorithm.n_gen == 20:
                sc = Scatter(title=algorithm.n_gen)
                sc.add(curve(problem), plot_type="line", color="black")
                sc.add(np.column_stack([pop.get("X"), F[:, 0]]), color="purple")
                sc.add(np.column_stack([pop[survivors].get("X"), pop[survivors].get("F")]), color="red", s=40,
                       marker="x")
                sc.do()
                plt.ylim(0, 2)
                plt.show()
                plt.close()

            # update the survivors and remaining individuals
            individual = pop[S]
            neighbors = pop[D[S].argsort()[:n_neighbors]]

            # if individual has had neighbors before update them
            N = individual.get("neighbors")
            if N is not None:
                neighbors = Population.merge(neighbors, N)
                neighbors = neighbors[neighbors.get("F")[:, 0].argsort()[:n_neighbors]]

            individual.set("neighbors", neighbors)
            individual.set("rank", cnt)

            survivors.append(S)
            remaining = [k for k in remaining if k != S]

            cnt += 1

        return pop[survivors]


class NeighborBiasedMating(Mating):

    def __init__(self, selection, crossover, mutation, bias=0.7, **kwargs):
        super().__init__(selection, crossover, mutation, **kwargs)
        self.bias = bias

    def _do(self, problem, pop, n_offsprings, parents=None, **kwargs):
        rnd = np.random.random(n_offsprings)
        n_neighbors = (rnd <= self.bias).sum()

        other = super()._do(problem, pop, n_offsprings - n_neighbors, parents, **kwargs)

        N = []

        cand = TournamentSelection(comp_by_rank).do(pop, n_neighbors, n_parents=1)[:, 0]
        for k in cand:
            N.append(pop[k])

            n_cand_neighbors = pop[k].get("neighbors")
            rnd = np.random.permutation(len(n_cand_neighbors))[:self.crossover.n_parents - 1]
            [N.append(e) for e in n_cand_neighbors[rnd]]

        parents = np.reshape(np.arange(len(N)), (-1, self.crossover.n_parents))
        N = Population.create(*N)

        bias = super()._do(problem, N, n_neighbors, parents, **kwargs)

        return Population.merge(bias, other)


parse_doc_string(MMGA.__init__)

if __name__ == '__main__':
    problem = MultiModalSimple2()

    algorithm = MMGA(
        pop_size=20,
        eliminate_duplicates=True)

    ret = minimize(problem,
                   algorithm,
                   termination=('n_gen', 100),
                   seed=1,
                   save_history=True,
                   verbose=False)


    def plot(algorithm):
        pop = algorithm.pop
        sc = Scatter(title=algorithm.n_gen)
        sc.add(curve(algorithm.problem), plot_type="line", color="black")
        sc.add(np.column_stack([pop.get("X"), pop.get("F")]), color="red")
        sc.do()


    plot(ret.algorithm)
    plt.show()

    with Video(File("mm.mp4")) as vid:
        for entry in ret.history:
            plot(entry)
            vid.record()


