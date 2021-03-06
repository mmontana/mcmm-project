r"""
This module should handle the analysis of an estimated Markov state model.
"""

from __future__ import absolute_import, division, print_function, unicode_literals
__metaclass__ = type

from .common import *

import numpy as np
import msmtools.analysis
import pandas as pd

import math

class CommunicationClass:
    def __init__(self, states, closed):
        self.states = states
        self.closed = closed
        

class MarkovStateModel:

    def __init__(self, transition_matrix, lagtime=1):
        """Create new Markov State Model.

        Parameters:
        transition_matrix: pandas.DataFrame
            Matrix where entry (a,b) contains transition probability a -> b
        """
        if not self.is_stochastic_matrix(transition_matrix):
            raise InvalidValue('Transition matrix must be stochastic')
        if not transition_matrix.shape[0] == transition_matrix.shape[1]:
            raise InvalidValue('Transition matrix must be quadratic')
        if not (transition_matrix.columns == transition_matrix.index).all():
            raise InvalidValue('Transition matrix must have identical row and column labels')

        self._lagtime = lagtime
        self._states = transition_matrix.index
        self._transition_matrix = transition_matrix
        self._backward_transition_matrix = None
        self._stationary_distribution = None
        self._num_states = transition_matrix.shape[0]
        self._is_aperiodic = None
        self._eigenvalues = None
        self._left_eigenvectors = None
        self._right_eigenvectors = None
        self._communication_classes = None

    @property
    def states(self):
        return list(self._states)

    @property
    def lagtime(self):
        return self._lagtime

    @property
    def communication_classes(self):
        """The set of communication classes of the state space.
        
        Returns: [CommunicationClass]
            List of communication classes sorted by size descending.
        """
        if self._communication_classes is None:
            self._communication_classes = [
                CommunicationClass(sorted(c), component_is_closed(c, self.transition_matrix))
                for c in strongly_connected_components(self.transition_matrix)
            ]
        self._communication_classes.sort(key=lambda c: len(c.states), reverse=True)
        return self._communication_classes
    
    @property
    def is_irreducible(self):
        """Whether the markov chain is irreducible."""
        return (len(self.communication_classes) == 1)
    
    @property
    def is_aperiodic(self):
        """Whether the markov chain is aperiodic."""
        if self._is_aperiodic is None:
            self._is_aperiodic = self._determine_aperiodicity()
        return self._is_aperiodic
    
    def _determine_aperiodicity(self):
        period = -1
        irred = self.is_irreducible                                     # remember, if chain is irreducible
        for s in range (0, self._num_states):                           # we check period for all states
            pos = np.zeros(self._num_states)
            pos[s] = 1                                                  # we are only in state s right at the start
            for i in range(1, 2*self._num_states):                      # we need to check all paths of length <= 2|S| - 1
                pos = pos.dot(self._transition_matrix)                     # propagate
                pos[:] = pos[:] > 0                                     # normalize to avoid too small entries
                if pos[s] == 1:
                    period = gcd(i, period) if not period == -1 else i  # period of this state = gcd of all path lengths
                if period == 1:
                    if irred:                                           # irreducible chains with one state with period == 1 are aperiodic
                        return True
                    break
            if not period == 1:                                         # if there is a state with period > 1, chain is not aperiodic
                return False
            else:
                period = -1
        return True

    @property
    def transition_matrix(self):
        """The transition matrix where entry (a,b) denotes transition probability a->b.
        
        Returns: pandas.DataFrame
        """
        return self._transition_matrix
    
    @property
    def backward_transition_matrix(self):
        """The backwards transition matrix.
        
        Returns: pandas.DataFrame
        """
        if self._backward_transition_matrix is None:
            pi = self.stationary_distribution
            self._backward_transition_matrix = self.transition_matrix.T.mul(pi, axis=1).mul(1/pi, axis=0)
        return self._backward_transition_matrix
    
    @property
    def period(self):
        """The period of the markov chain. The markov chain is required to be irreducible.
        
        Returns: int
        """
        if not self.is_irreducible:
            raise InvalidOperation('Cannot compute period of reducible Markov chain')
        eigenvalues, _ = self.left_eigen
        norms = np.absolute(eigenvalues)
        period = np.count_nonzero(np.isclose(norms, 1))
        assert(period >= 1)
        return period

    @property
    def stationary_distribution(self):
        """The unique stationary distribution. The Markov chain must be irreducible.
        
        Type: pandas.Series
        """
        if self._stationary_distribution is None:
            self._stationary_distribution = self._find_stationary_distribution()
        return self._stationary_distribution
       

    def left_eigenvectors(self, k=None):
        """Computes the first k left eigenvectors for largest eigenvalues
        
        Arguments:
        k: int
            How many eigenvectors should be returned. Defaults to None, meaning all.
        
        Returns: pandas.DataFrame
            DataFrame containing the eigenvectors as columns
        """
        if k is None:
            k = len(self.transition_matrix)
        return self.left_eigen[1].iloc[:,:k]
    
    def right_eigenvectors(self, k=None):
        """Computes the first k right eigenvectors for largest eigenvalues
        
        Arguments:
        k: int
            How many eigenvectors should be returned. Defaults to None, meaning all.
        
        Returns: pandas.DataFrame
            DataFrame containing the eigenvectors as columns
        """
        if k is None:
            k = len(self.transition_matrix)
        return self.right_eigen[1].iloc[:,:k]
    
    @property
    def is_reversible(self):
        """Whether the markov chain is reversible"""
        return np.allclose(self.backward_transition_matrix, self.transition_matrix)
    
    def _right_eigen(self, matrix):
        eigenvalues, eigenvectors = np.linalg.eig(matrix)
        # sort by eigenvalues descending:
        eigenvalues, eigenvectors = zip(*(
            sorted(zip(eigenvalues, eigenvectors.T), key=lambda x: np.real(x[0]), reverse=True)
        ))
        eigenvalues = pd.Series(eigenvalues)
        eigenvectors = pd.concat([
            pd.Series(x, index=matrix.index)
            for x in eigenvectors
        ], axis=1)
        return (eigenvalues, eigenvectors)

    @property
    def left_eigen(self):
        """Finds the eigenvalues and left eigenvectors of the transition matrix.
        
        Returns: (eigenvalues, eigenvectors) = (pandas.Series, pandas.DataFrame)
            where eigenvalues[i] corresponds to eigenvectors[:,i]
        """
        if self._left_eigenvectors is None:
            self._eigenvalues, self._left_eigenvectors = self._right_eigen(self.transition_matrix.T)
        return (self._eigenvalues, self._left_eigenvectors)

    @property
    def right_eigen(self):
        """Finds the eigenvalues and right eigenvectors of the transition matrix.
        
        Returns: (eigenvalues, eigenvectors) = (pandas.Series, pandas.DataFrame)
            where eigenvalues[i] corresponds to eigenvectors[:,i]
        """
        if self._right_eigenvectors is None:
            self._eigenvalues, self._right_eigenvectors = self._right_eigen(self.transition_matrix)
        return (self._eigenvalues, self._right_eigenvectors)

    @property
    def eigenvalues(self):
        return self.left_eigen[0]
            
    def _find_stationary_distribution(self):
        """Finds the stationary distribution of a given stochastic matrix.
        The matrix is assumed to be irreducible.
        """
        if not self.is_irreducible:
            raise InvalidOperation('Cannot compute stationary distribution of reducible Markov chain')
        eigenvalues, eigenvectors = self.left_eigen
        v = eigenvectors.iloc[:,np.isclose(eigenvalues, 1)].squeeze()
        assert(len(v.shape) == 1)
        v_real = v.apply(np.real)
        assert(np.allclose(v, v_real)) # result should be real
        return v_real/np.sum(v_real)

    @property
    def implied_timescales(self):
        return self.eigenvalues.iloc[1:].apply(lambda x: - self.lagtime / math.log(abs(x)))
    
    def forward_committors(self, A, B):
        """Returns the vector of forward commitors from A to B
        
        Returns: pandas.Series
        """
        return self._commitors(A, B, self.transition_matrix)
    
    def backward_commitors(self, A, B):
        """Returns the vector of backward commitors from A to B"""
        return self._commitors(B, A, self.backward_transition_matrix)

    def probability_current(self, A, B):
        """Returns the probability current from A to B.

        Returns:
        (n, n) pandas.DataFrame containing the probabilty currents for every pair of states.
        """
        result = pd.DataFrame(np.zeros(self.transition_matrix.shape),
            index=self._states, columns=self._states
        )
        fwd_commitors = self.forward_committors(A, B)
        bwd_commitors = self.backward_commitors(A, B)
        for i in self._states:
            for j in self._states:
                if i != j:
                    result.at[i,j] = self.stationary_distribution.at[i] * bwd_commitors.at[i] * self.transition_matrix.at[i,j] * fwd_commitors.at[j]
        return result

    def effective_probability_current(self, A, B):
        """Returns the effective probabiltiy current from A to B.

        Returns:
        (n, n) pandas.DataFrame containing the effective probabilty currents for every pair of states.
        """
        current = self.probability_current(A, B)
        result = pd.DataFrame(np.zeros(current.shape), index=current.index, columns=current.columns)
        for i in current.index:
            for j in current.columns:
                result.at[i,j] = max(0, current.at[i,j]-current.at[j,i])
        return result

    def transition_rate(self, A, B):
        """Returns the transition rate from A to B"""
        current = self.probability_current(A, B)
        num_trajs = current.loc[A,:].sum().sum()
        result = num_trajs / self.stationary_distribution.dot(self.backward_commitors(A,B))
        return result

    def mean_first_passage_time(self, A, B):
        """Returns the mean first-passage-time from A to B"""
        return 1/self.transition_rate(A, B)

    def pcca(self, num_sets):
        """Compute membership probability matrix using PCCA++.

        Arguments:
        num_sets: integer
            Number of metastable sets

        Returns:
        clusters : pandas.DataFrame
            Membership vectors. clusters.loc[i, j] contains the membership probability of state i to metastable state j.
        """
        if not self.is_reversible:
            raise InvalidOperation('Can not perform PCCA on non-reversible markov chain.')
        if num_sets > self._num_states:
            raise InvalidValue('Number of metastable sets exceeds number of states')

        pcca = msmtools.analysis.pcca(self.transition_matrix, num_sets)
        return pd.DataFrame(pcca, index=self._states)
    
    def metastable_set_assignments(self, num_sets):
        """Performs PCCA++ and returns assignment vector, i.e. a vector with num_states entries,
        that are the most probable metastable set for every corresponding state.
        
        Arguments:
        num_sets: integer
            Number of metastable sets

        Returns: pandas.Series
            Series where the entry.loc[i] contains the metastable set of state i.
        """
        pcca_mat = self.pcca(num_sets)
        return pd.Series([pcca_mat.loc[i, :].argmax() for i in self._states], index=self._states)

    def metastable_sets(self, num_sets):
        """Performs PCCA++ and returns the metastable sets.
        
        Arguments:
        num_sets: integer
            Number of metastable sets

        Returns: [[state]]
            List of metastable sets, each of which is a list of states.
        """
        pcca_mat = self.pcca(num_sets)
        sets = [[] for i in range(num_sets)]
        for s in self._states:
            sets[pcca_mat.loc[s, :].argmax()].append(s)
        return sets
    
    def restriction(self, communication_class):
        """Returns the restriction of the model to a single communication class.
        
        Arguments:
        communication_class: CommunicationClass
            The model's communication classes that the result should be restricted to. Required to be closed.
        
        Returns: MarkovStateModel
            The restricted markov chain. Note that the states will be re-indexed to range [0, n]
        """
        assert(communication_class.closed)
        return type(self)(self.transition_matrix.loc[communication_class.states, communication_class.states])

    def _commitors(self, A, B, T):
        """Returns the vector of forward commitors from A to B given propagator T"""
        n = len(T)
        C = list(set(self._states) - set().union(A, B))
        if C:
            M = T - np.identity(n)
            d = M.loc[C,B].sum(axis=1)
            solution = np.linalg.solve(M.loc[C, C], -d)
        result = pd.Series(np.empty(n), index=self._states)
        c = 0
        for i in result.index:
            if i in A:
                result.at[i] = 0
            elif i in B:
                result.at[i] = 1
            else:
                result.at[i] = np.real(solution[c])
                assert(np.isclose(result.at[i], solution[c])) # solution should be real
                c += 1
        return result

    @staticmethod
    def is_stochastic_matrix(A):
        return np.all(0 <= A) and np.all(A <= 1) and np.allclose(np.sum(A, axis=1), 1)
    

def depth_first_search(adjacency_matrix, root, flags):
    """Performs depth-first search on a digraph.
    
    Parameters:
    adjacency_matrix: pandas.DataFrame containing node-node adjancencies.
    root: Root node index
    flags: List of vertex flags. All vertices whose flag is initially set are ignored. After return the flags of all found vertices will be set.
    
    Returns a list of all node indices reachable from root sorted by
    post-order traversal.
    """
    result = []
    flags[root] = True
    for vertex in range(adjacency_matrix.shape[0]):
        if adjacency_matrix.iat[root, vertex]:
            if not flags[vertex]:
                result += depth_first_search(adjacency_matrix, vertex, flags)
    result.append(root)
    return result


def component_is_closed(component, adjacency_matrix):
    """Returns whether a component is closed, i.e. whether there are no
    edges pointing out of the component
    """
    for a in component:
        for b in set(adjacency_matrix.index).difference(component):
            if adjacency_matrix.at[a,b] > 0:
                return False
    return True


def strongly_connected_components(adjacency_matrix):
    """Finds all strongly connected components of a digraph.
    
    Parameters:
    adjacency_matrix: pandas.DataFrame containing node-node adjancencies.
    
    Returns a list of strongly connected components, each of which is a list of vertex labels.
    """
    nodes = range(adjacency_matrix.shape[0])
    flags = [False] * len(nodes)
    node_list = []
    for node in nodes:
        if not flags[node]:
            node_list += depth_first_search(adjacency_matrix, node, flags)
    flags = [False] * len(nodes)
    components = []
    for node in reversed(node_list):
        if not flags[node]:
            components.append([adjacency_matrix.index[i] for i in depth_first_search(adjacency_matrix.T, node, flags)])
    return components


def gcd(a, b):
    while b != 0:
        b, a = a%b, b
    return a
