#!/usr/bin/env python3
import sys
import argparse
from graph_tool.all import *



def prepare_gt_graph_draw(g):
    comp, hist = label_components(g, directed=False)
    pos = sfdp_layout(g, epsilon=0.0001, C=0.1, gamma=1.8, verbose=True, max_iter=10000)
    return {
        'pos': pos,
        'vertex_fill_color': comp
    }



def main(args):
    parser = argparse.ArgumentParser(
        description='visualize network using graph_tool (for coordination project)'
    )

    parser.add_argument('-i', '--infile',
        action="store", dest="infile", type=str, required=True,
        help="path to input pickle file of filtered interaction")
    parser.add_argument('-o', '--outfile',
        action="store", dest="outfile", type=str, required=True,
        help="path to output pdf of the network")

    args = parser.parse_args(args)
    infile = args.infile
    outfile = args.outfile

    try:
        # read input
        g = load_graph(infile)
        # do work
        param_dict = prepare_gt_graph_draw(g)
        # write output
        graph_draw(g, output=outfile, **param_dict)

    except Exception:
        with open(outfile, 'a') as f:
            pass



if __name__ == '__main__': main(sys.argv[1:])
