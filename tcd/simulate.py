#!/usr/bin/env python3
import sys
import random
import argparse
import pandas as pd
from tqdm import tqdm
from os.path import join
from numpy.random import shuffle, random_sample



class BatchRNG():
    def __init__(self, batch_size=10000):
        self._cur_idx = 0
        self._batch_size = batch_size
        self._random_numbers = random_sample(size=batch_size)

    def __iter__(self):
        return self

    def __next__(self):
        if self._cur_idx >= self._batch_size:
            self._random_numbers = random_sample(size=self._batch_size)
            self._cur_idx = 0
        return self._random_numbers[self._cur_idx]

    def next(self):
        return self.__next__()



def left_index(i):
    return 2 * i + 1

def right_index(i):
    return 2 * i + 2

class WeightedShuffler():
    @classmethod
    def build_weights(cls, nodes, weights, n, i=0):
        if i >= n:
            return 0

        this_weight = weights[i]
        if this_weight <= 0:
            raise ValueError("weight can't be zero or negative")

        left_weight = cls.build_weights(nodes, weights, n, left_index(i))
        right_weight = cls.build_weights(nodes, weights, n, right_index(i))

        nodes[i] = [this_weight, left_weight, right_weight]

        return this_weight + left_weight + right_weight

    def __init__(self, strength_dict, rng=None):
        if rng is None:
            self._rng = BatchRNG()
        else:
            self._rng = rng

        self._items = [nid for nid in strength_dict]
        self._weights = [strength_dict[nid] for nid in self._items]

        n = len(self._items)
        self._tree_nodes = [None for _ in range(n)]

        WeightedShuffler.build_weights(self._tree_nodes, self._weights, n)

    def sample(self, i=0):
        nodes = self._tree_nodes

        this_w, left_w, right_w = nodes[i]
        total = this_w + left_w + right_w
        r = total * self._rng.next()
        if r < this_w:
            nodes[i][0] -= 1
            print(nodes)
            return self._items[i]
        elif r < this_w + left_w:
            nodes[i][1] -= 1
            return self.sample(left_index(i))
        else:
            nodes[i][2] -= 1
            return self.sample(right_index(i))




def rewire_bipartite(edge_df, p1_col, p2_col, w_col, num_sim):
    '''
        rewire the bipartite graph (p1, p2, w)

        input:
            edge_df : dataframe that contains (p1, p2, w)
            p1_col : column name that represent p1
            p2_col : column name that represent p2
            w_col : column name that represent weight
            num_sim : number of simulations

        return:
            random_edge_df : rewired version of edge_df

        assumption:
            1. non-empty inputs: edge_df
            2. weights are integers i.e. induced by counting

        notes:
            Simple random rewiring ignores assortivity of the graph
    '''
    # strengths
    p1_S = edge_df.groupby(p1_col)[w_col].sum()
    num_node_p1 = len(p1_S)
    p2_S = edge_df.groupby(p2_col)[w_col].sum()
    p2_nodes = pd.Series(p2_S.index)

    # this step takes too much memory
    p2_seq = p2_nodes.repeat(p2_S).values

    for _ in tqdm(range(num_sim), desc="running simulations", total=num_sim):
        # random permutation of edges according to strength
        shuffle(p2_seq)

        random_edges = dict()
        current_idx = 0
        for p1_node in tqdm(p1_S.index, desc="rewiring graph", total=num_node_p1):
            k = p1_S[p1_node]

            sampled_p2_nodes = p2_seq[current_idx:current_idx+k]
            for p2_node in sampled_p2_nodes:
                # increment weight of sampled edge
                edge_key = (p1_node, p2_node)
                random_edges[edge_key] = random_edges.get(edge_key, 0)+1
            current_idx += k

        # form random edge df and filter on target p1 nodes
        random_edge_df = pd.DataFrame.from_records([
            # (p1_node, p2_node, weight)
            (edge_key[0], edge_key[1], edge_weight)
            for edge_key, edge_weight in random_edges.items()
        ], columns=[p1_col, p2_col, w_col])

        yield random_edge_df



def main(args):
    parser = argparse.ArgumentParser(
        description='simulate random rewiring of a bipartite graph',
    )

    parser.add_argument('-i', '--infile',
        action="store", dest="infile", type=str, required=True,
        help="path to input parquet file of edge table")
    parser.add_argument('-o', '--outdir',
        action="store", dest="outdir", type=str, required=True,
        help="path to output directory for output simulated edge tables")
    parser.add_argument('-n', '--numsim',
        action="store", dest="numsim", type=int, required=True,
        help="number of simulations")
    parser.add_argument('--p1col',
        action="store", dest="p1col", type=str, required=True,
        help="column name of nodes in partition 1")
    parser.add_argument('--p2col',
        action="store", dest="p2col", type=str, required=True,
        help="column name of nodes in partition 2")
    parser.add_argument('--wcol',
        action="store", dest="wcol", type=str, required=True,
        help="column name of edge weights")

    args = parser.parse_args(args)
    infile = args.infile
    outdir = args.outdir
    p1_col = args.p1col
    p2_col = args.p2col
    w_col = args.wcol
    numsim = args.numsim

    # read input
    edge_df = pd.read_parquet(infile)

    # do work
    work_iter = rewire_bipartite(edge_df, p1_col, p2_col, w_col, numsim)
    for sim_idx, random_edge_df in enumerate(work_iter):
        # write output
        fname = "{}.edge.parquet".format(sim_idx)
        random_edge_df.to_parquet(join(outdir, fname))



def test():
    nodes = {'1': 2, '2': 2, '3': 2}
    counter = dict()
    for _ in range(100):
        shuffler = WeightedShuffler(nodes)
        results = tuple([shuffler.sample() for e in range(6)])
        print(results)

        counter[results] = counter.get(results, 0)+1
    print(counter)


#if __name__ == '__main__': main(sys.argv[1:])
if __name__ == '__main__': test()
