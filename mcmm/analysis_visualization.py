from __future__ import absolute_import, division, print_function, unicode_literals
__metaclass__ = type

from mcmm import analysis as ana
import numpy as np
import math
import matplotlib.pyplot as plt


class AnalysisViz(object):
    '''
    Class serving as a wrapper for matplotlib corresponding with mcmm.analysis classes to provide
    visualiziation defaults.
    '''

    def __init__(self, msm):
        self._msm = msm
        
    def _format_square(ax):
        ax.set_xlim(-2, 2)
        ax.set_ylim(-2, 2)
        ax.set_xticks([-2, -1, 0, 1, 2])
        ax.set_yticks([-2, -1, 0, 1, 2])
        ax.set_xlabel(r"$x$ / a.u.")
        ax.set_ylabel(r"$y$ / a.u.")
        ax.set_aspect('equal')

    def plot_network(self, state_pos, num_metastable_sets):
        '''
        Produces a 2D-plot of the network obtained after PCCA and TPT Analysis.
        Parameters:
        
            state_pos : (n, 2) ndarray. positions of states (cluster centers)
            num_metastable_sets : integer. Number of metastable sets of the Markov State Model,
                we should perform PCCA with
        '''
            
        ####################
        # Perform Analyses #
        ####################
        
        data_dim = 2
        pcca_mat = self._msm.pcca(num_metastable_sets)
        barycenters = np.zeros((num_metastable_sets, data_dim))
        sets = self._msm.metastable_sets(num_metastable_sets)
        for i in range(num_metastable_sets): #loop over metastable sets
            barycenters[i, :] = [np.mean(state_pos[sets[i], j]) for j in range(data_dim)]
        pi = np.array([self._msm.stationary_distribution[s].sum() for s in sets])
        
        
        ########
        # Plot #
        ########
        
        fig, ax = plt.subplots(figsize=(5, 5))
        full_edge_size = 70
        full_node_size = 6
        arrow_curvature = 0.3
        arrow_brightness = 0.2
        
        # draw nodes
        node_size = [full_node_size * pi[i] for i in range(num_metastable_sets)]
        circles = []
        for i in range(num_metastable_sets):
            fig = plt.gcf()
            c = plt.Circle(barycenters[i,:], radius = math.sqrt(0.5*node_size[i])/2.0, 
                           antialiased=True, facecolor='blue', edgecolor='black')
            circles.append(c)
            fig.gca().add_artist(c)
            
        # draw edges
        for i in range(num_metastable_sets):
            for j in range(num_metastable_sets):
                if i is not j:
                    egde_size = full_edge_size*self._msm.transition_rate(sets[i],sets[j])
                    #egde_size = 1
                    dist = math.sqrt((barycenters[i, 0] - barycenters[j, 0])**2
                                    + (barycenters[i, 1] - barycenters[j, 1])**2)
                    #print(i, "->", j, ": ", dist)
                    curv = arrow_curvature / dist
                    ax.annotate("",
                        xy=(barycenters[i, 0], barycenters[i, 1]), xycoords='data',
                        xytext=(barycenters[j, 0], barycenters[j, 1]), textcoords='data',
                        arrowprops=dict(arrowstyle='simple,head_length=%f,head_width=%f,tail_width=%f'
                                        % (max(0.5, 2*egde_size), max(0.5, 2*egde_size), egde_size),
                        color='%f'%arrow_brightness,
                        patchA=circles[j],
                        patchB=circles[i],
                        #shrinkB=node_size[i]/full_node_size*100,
                        connectionstyle="arc3,rad=%f" % curv,
                        ),
                    )
        _format_square(ax)
        fig.tight_layout()