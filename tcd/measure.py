#!/usr/bin/env python3
import sys
import glob
import argparse
import numpy as np
import pandas as pd
import sparse_dot_topn.sparse_dot_topn as ct
from tqdm import tqdm
from os.path import join
from itertools import combinations
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer



def dummy_func(doc): return doc



class DocConverter(object):
    def __init__(self):
        self._p1_idx_map = None

    def edge2doc(self, edge_df, p1_col, p2_col, w_col):
        self._p1_idx_map = dict()
        idx = 0
        for p1_node, grp in edge_df.groupby(p1_col):
            self._p1_idx_map[p1_node] = idx
            idx += 1
            yield grp[p2_col].repeat(grp[w_col]).values
        raise StopIteration



def dot_top(A, B, ntop, lower_bound=0):
    '''
        from https://towardsdatascience.com/fuzzy-matching-at-scale-84f2bfd0c536
    '''
    # force A and B as a CSR matrix.
    # If they have already been CSR, there is no overhead
    A = A.tocsr()
    B = B.tocsr()
    M, _ = A.shape
    _, N = B.shape

    idx_dtype = np.int32

    nnz_max = M*ntop

    indptr = np.zeros(M+1, dtype=idx_dtype)
    indices = np.zeros(nnz_max, dtype=idx_dtype)
    data = np.zeros(nnz_max, dtype=A.dtype)
    ct.sparse_dot_topn(
        M, N, np.asarray(A.indptr, dtype=idx_dtype),
        np.asarray(A.indices, dtype=idx_dtype),
        A.data,
        np.asarray(B.indptr, dtype=idx_dtype),
        np.asarray(B.indices, dtype=idx_dtype),
        B.data,
        ntop,
        lower_bound,
        indptr, indices, data)
    return csr_matrix((data,indices,indptr),shape=(M,N))



def calculate_interaction(edge_df, p1_col, p2_col, w_col,
        node1_col, node2_col, sim_col, sup_col,
        tqdm_total=None, tqdm_desc="calculating interaction"):
    '''
        calculate interactions between nodes in partition 1

        input:
            edge_df : dataframe that contains (p1, p2, w)
            p1_col : column name that represent p1
            p2_col : column name that represent p2
            w_col : column name that represent weight, if None it's unweighted

        return:
            interactions : dict { (p1_node1, p1_node2) : interaction_weight }

        assumption:
            1. non-empty inputs: edge_df
            2. p1_node1 < p1_node2 holds for the tuples in interactions
    '''
    user_ids, docs = zip(*(
        (p1_node, grp[p2_col].repeat(grp[w_col]).values)
        for p1_node, grp in edge_df.groupby(p1_col)
        if len(grp) > 1
    ))

    try:
        tfidf = TfidfVectorizer(
            analyzer='word',
            tokenizer=dummy_func,
            preprocessor=dummy_func,
            use_idf=True,
            token_pattern=None,
            lowercase=False,
            sublinear_tf=True,
            min_df=3,
        )
        docs_vec = tfidf.fit_transform(docs)
    except ValueError:
        tfidf = TfidfVectorizer(
            analyzer='word',
            tokenizer=dummy_func,
            preprocessor=dummy_func,
            use_idf=True,
            token_pattern=None,
            lowercase=False,
            sublinear_tf=True,
            min_df=1,
        )
        docs_vec = tfidf.fit_transform(docs)

    results = dot_top(docs_vec, docs_vec.T, ntop=100)

    # number of tweets/retweets as support
    supports = edge_df.groupby(p1_col)[w_col].sum().to_dict()

    interactions = pd.DataFrame.from_records([
        (u1, user_ids[u2_idx], sim,
            min(supports[user_ids[u1_idx]], supports[user_ids[u2_idx]]))
        for u1_idx, u1 in enumerate(user_ids)
        for u2_idx, sim in
        zip(
            results.indices[results.indptr[u1_idx]:results.indptr[u1_idx+1]],
            results.data[results.indptr[u1_idx]:results.indptr[u1_idx+1]]
        )
        if u1_idx < u2_idx
    ], columns=[node1_col, node2_col, sim_col, sup_col])

    return interactions



def main(args):
    parser = argparse.ArgumentParser(
        description='calculate p-values for interactions in a bipartite graph',
    )

    parser.add_argument('-i', '--infile',
        action="store", dest="infile", type=str, required=True,
        help="path to input parquet file of edge table")
    parser.add_argument('-o', '--outfile',
        action="store", dest="outfile", type=str, required=True,
        help="path to output file of interactions with p-values")
    parser.add_argument('--p1col',
        action="store", dest="p1col", type=str, required=True,
        help="column name of nodes in partite 1")
    parser.add_argument('--p2col',
        action="store", dest="p2col", type=str, required=True,
        help="column name of nodes in partite 2")
    parser.add_argument('--wcol',
        action="store", dest="wcol", type=str, required=True,
        help="column name of edge weights")
    parser.add_argument('--node1',
        action="store", dest="node1", type=str, required=True,
        help="column name of node1")
    parser.add_argument('--node2',
        action="store", dest="node2", type=str, required=True,
        help="column name of node2")
    parser.add_argument('--sim',
        action="store", dest="sim", type=str, required=True,
        help="column name of similarity")
    parser.add_argument('--sup',
        action="store", dest="sup", type=str, required=True,
        help="column name of support")

    args = parser.parse_args(args)
    infile = args.infile
    outfile = args.outfile
    p1_col = args.p1col
    p2_col = args.p2col
    w_col = args.wcol
    node1_col = args.node1
    node2_col = args.node2
    sim_col = args.sim
    sup_col = args.sup

    # read input
    edge_df = pd.read_parquet(infile)

    if len(edge_df) > 0 and np.any(edge_df.groupby(p1_col).size() > 1):
        # do work
        interaction_df = calculate_interaction(
                edge_df, p1_col, p2_col, w_col,
                node1_col, node2_col, sim_col, sup_col)
        # write output
        interaction_df.to_parquet(outfile)
    else:
        with open(outfile, 'a') as f:
            pass



if __name__ == '__main__': main(sys.argv[1:])
