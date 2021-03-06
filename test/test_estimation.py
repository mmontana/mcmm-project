from __future__ import absolute_import, division, print_function, unicode_literals
__metaclass__ = type

from mcmm import estimation as est, analysis as ana, clustering as cl
import numpy as np
import random
import unittest
from nose.tools import assert_true, assert_false, assert_equals, assert_raises
from numpy.testing import assert_array_equal


def test_compute_counting_matrix():
    # check simple example with 10 states and 3 clusters
    a = np.array([0, 2, 1, 2, 2, 1, 1, 1, 2, 1])
    matrix = est.Estimator(a, 3, 2).count_matrix
    assert_array_equal(np.array([[0, 0, 1], [0, 2, 0], [0, 1, 0]]), matrix)
    # check simple example with 10 states and 3 clusters, different lag_time
    a = np.array([0, 2, 1, 2, 2, 1, 1, 1, 2, 1])
    matrix = est.Estimator(a, 1, 1).count_matrix
    assert_array_equal(np.array([[0, 0, 1], [0, 2, 2], [0, 3, 1]]), matrix)
    # check simple example with 10 states and 2 clusters
    a = np.array([0, 1, 0, 1, 1, 0, 0, 0, 1, 0])
    matrix = est.Estimator(a, 1, 1).count_matrix
    assert_array_equal(np.array([[2, 3], [3, 1]]), matrix)
    # check simple example with 10 states and 2 clusters, maximal lag_time
    a = np.array([0, 1, 0, 1, 1, 0, 0, 0, 1, 0])
    matrix = est.Estimator(a, 9, 1).count_matrix
    assert_array_equal(np.array([[1, 0], [0, 0]]), matrix)
    # check simple example with 10 states and 2 clusters, high window shift
    a = np.array([0, 1, 0, 1, 1, 0, 0, 0, 1, 0])
    matrix = est.Estimator(a, 4, 6).count_matrix
    assert_array_equal(np.array([[0, 1], [0, 0]]), matrix)


def test_simple_markov():
    """This test generates data based on a small Markov model
    and tests the resulting transition matrix against the original transition matrix
    """
    A = np.array([[0.5, 0.3, 0.2], [0.2, 0.6, 0.2], [0.1, 0.05, 0.85]])
    n = 50000
    cluster_labels = np.zeros(n, dtype=np.dtype(int))
    cluster_labels[0] = 1;
    for i in range(1, n):
        zahl = np.random.rand(1)
        if zahl < A[cluster_labels[i - 1], 0]:
            cluster_labels[i] = 0
        elif zahl < A[cluster_labels[i - 1], 0] + A[cluster_labels[i - 1], 1]:
            cluster_labels[i] = 1
        else:
            cluster_labels[i] = 2
    estimator = est.Estimator(cluster_labels, 1, 1)
    np.testing.assert_allclose(estimator.transition_matrix, A, atol=0.05, rtol=0.1)


def test_clustering_estimation_simple_markov():
    """This test generates randomly perturbed data based on a transition matrix. Then we do clustering.
    Then we check if the estimated matrix behaves as expected.
    """
    A = np.array([[0.5, 0.4, 0.1, 0], [0.2, 0.8, 0, 0], [0, 0.05, 0.25, 0.7], [0, 0, 0.75, 0.25]])
    for i, row in enumerate(A):
        A[i] = row / sum(row)
    n = 10000
    states = np.zeros((n, 1))
    states[0, 0] = 1
    factor = 0.001
    for i in range(1, n):
        zahl = np.random.rand(1)
        if zahl < A[int(states[i - 1, 0]), 0]:
            states[i, 0] = 0 + factor * np.random.rand()
        elif zahl < A[int(states[i - 1, 0]), 0] + A[int(states[i - 1, 0]), 1]:
            states[i, 0] = 1 + factor * np.random.rand()
        elif zahl < A[int(states[i - 1, 0]), 0] + A[int(states[i - 1, 0]), 1] + A[int(states[i - 1, 0]), 2]:
            states[i, 0] = 2 + factor * np.random.rand()
        else:
            states[i, 0] = 3 + factor * np.random.rand()
    # do the clustering
    clustering = cl.KMeans(states, 4, method='kmeans++')
    cluster_centers = clustering.cluster_centers
    cluster_labels = clustering.cluster_labels
    cluster_labels = np.array(cluster_labels)
    # do the estimation
    estimator = est.Estimator(cluster_labels, 1, 1)
    matrix = estimator.transition_matrix
    Q = np.identity(4)
    Qt = Q
    for i in range(0, 4):
        index = np.argmax(cluster_centers)
        cluster_centers[index] = cluster_centers[index] - 10
        P = np.identity(4)
        # permute row and column index with 3-i
        if 3 - i != index:
            P[3 - i, 3 - i] = 0
            P[index, index] = 0
            P[index, 3 - i] = 1
            P[3 - i, index] = 1
        z = cluster_centers[3 - i, 0]
        cluster_centers[3 - i] = cluster_centers[index, 0]
        cluster_centers[index, 0] = z
        Q = P.dot(Q)
        Qt = Qt.dot(P)
    matrix = Q.dot(matrix).dot(Qt)
    np.testing.assert_allclose(matrix, A, atol=0.05, rtol=0.1)


def test_clustering_estimation_bigger_markov():
    """This test generates randomly perturbed data based on a transition matrix. Then we do clustering.
    Then we check if the estimated matrix behaves as expected.
    Just as test_clustering_estimation_simple_markov(), but with an arbitrary bigger random matrix
    """
    m = 10  # size of original transition matrix, free to choose
    A = np.random.rand(m, m) + 0.001
    for i, row in enumerate(A):
        A[i] = row / sum(row)
    n = 100000  # number of random evaluations of the Markov process
    states = np.zeros((n, 1))
    states[0, 0] = 1
    factor = 0.001
    for i in range(1, n):
        check = 0
        summe = 0
        zahl = np.random.rand(1)
        while check < m:
            summe = summe + A[int(states[i - 1, 0]), check]
            if zahl < summe:
                states[i, 0] = check + factor * np.random.rand()
                check = m + 1
            check = check + 1
    # do the clustering
    clustering = cl.KMeans(states, m, method='kmeans++')
    cluster_centers = clustering.cluster_centers
    cluster_labels = clustering.cluster_labels
    cluster_labels = np.array(cluster_labels)
    # do the estimation
    estimator = est.Estimator(cluster_labels, 1, 1)
    matrix = estimator.transition_matrix
    Q = np.identity(m)
    Qt = Q
    for i in range(0, m):
        index = np.argmax(cluster_centers)
        cluster_centers[index] = cluster_centers[index] - 10
        P = np.identity(m)
        # permute row and column index with m-1-i
        if m - 1 - i != index:
            P[m - 1 - i, m - 1 - i] = 0
            P[index, index] = 0
            P[index, m - 1 - i] = 1
            P[m - 1 - i, index] = 1
        z = cluster_centers[m - 1 - i, 0]
        cluster_centers[m - 1 - i] = cluster_centers[index, 0]
        cluster_centers[index, 0] = z
        Q = P.dot(Q)
        Qt = Qt.dot(P)
    matrix = Q.dot(matrix).dot(Qt)
    print(np.linalg.norm(A - matrix))
    np.testing.assert_allclose(matrix, A, atol=0.05, rtol=0.1)


def test_transition_matrix():
    clusters = 10
    traj = np.random.randint(0, clusters, 200)
    transition_matrix = est.Estimator(traj, 1, 1).transition_matrix
    row_sums = transition_matrix.sum(axis=1)
    np.testing.assert_allclose(row_sums, 1)


def test_transition_matrix_reversible():
    traj = np.random.randint(0, 10, 200)
    transition_matrix = est.Estimator(traj, 1, 1).reversible_transition_matrix
    msm = ana.MarkovStateModel(transition_matrix)
    assert_true(msm.is_reversible)

def test_multiple_trajectories():
    trajs = [
        np.array([0, 1, 2, 3, 2]),
        np.array([1, 3, 1, 3]),
        np.array([2, 0, 4, 1, 4, 0])
    ]
    estimator = est.Estimator(trajs)
    np.testing.assert_allclose(estimator.count_matrix, np.array([
        [0, 1, 0, 0, 1],
        [0, 0, 1, 2, 1],
        [1, 0, 0, 1, 0],
        [0, 1, 1, 0, 0],
        [1, 1, 0, 0, 0]
    ]))
