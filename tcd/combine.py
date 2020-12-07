#!/usr/bin/env python3
import sys
import glob
import pickle
import pyarrow
import argparse
import numpy as np
import pandas as pd
import networkx as nx
from networkx.algorithms.centrality import eigenvector_centrality_numpy
from tqdm import tqdm



def main(args):
    parser = argparse.ArgumentParser(
        description='filter and aggregate end results'
    )

    parser.add_argument('-i', '--interaction',
        action="store", dest="interaction", type=str, required=True,
        help="path to input parquet file of interaction")
    parser.add_argument('-t', '--twttext',
        action="store", dest="twttext", type=str, required=False,
        help="path to input indexed text of tweets")
    parser.add_argument('-o', '--outgraph',
        action="store", dest="outgraph", type=str, required=True,
        help="path to output file of the graphml for gephi vis")
    parser.add_argument('-g', '--grouptext',
        action="store", dest="grouptext", type=str, required=True,
        help="path to output file of context of each suspicious groups")
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
    interaction = args.interaction
    twttext = args.twttext
    outgraph = args.outgraph
    grouptext = args.grouptext
    node1 = args.node1
    node2 = args.node2
    sim = args.sim
    sup = args.sup

    # read input
    try:
        interaction_df = pd.read_parquet(interaction)
        interaction_df = interaction_df[
            interaction_df[sup] > interaction_df[sup].median()
        ]
    except pyarrow.lib.ArrowIOError:
        interaction_df = list()

    has_text = twttext is not None
    if has_text:
        with open(twttext, 'rb') as f:
            tweet_table = pickle.load(f)

    if len(interaction_df) > 0:
        # do work
        G = nx.Graph()
        for idx, row in interaction_df.iterrows():
            G.add_edge(row[node1], row[node2], weight=row[sim], support=row[sup])
        # write graph object
        nx.write_graphml_lxml(G, outgraph)
        del interaction_df

        try:
            centrality = pd.Series(eigenvector_centrality_numpy(G, max_iter=100))
        except TypeError:
            # null input -> null output
            with open(outgraph, 'a') as f:
                pass
            with open(grouptext, 'a') as f:
                pass
            return

        centrality_filter = lambda node: centrality.loc[node] > 0.5

        filtered_G = nx.subgraph_view(G, filter_node=centrality_filter)
        if not has_text:
            tweet_table = dict()
        texts = [
            {
                node_id: tweet_table.get(node_id, '')
                for node_id in component
            }
            for component in nx.connected_components(filtered_G)
        ]
        if has_text:
            texts.sort(key=len, reverse=True)
        with open(grouptext, 'wb') as f:
            pickle.dump(texts, f)

    else:
        # null input -> null output
        with open(outgraph, 'a') as f:
            pass
        with open(grouptext, 'a') as f:
            pass



if __name__ == '__main__': main(sys.argv[1:])
