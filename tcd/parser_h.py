#!/usr/bin/env python3
import re
import sys
import gzip
import argparse
import pandas as pd
import simplejson as json
from tqdm import tqdm
from os.path import join
from collections import defaultdict, Counter



SOURCE_REGEX = re.compile(r'<a href=(?:\\*)\"(.+)(?:\\*)\" rel=(?:\\*)\"(.*)(?:\\*)\">(.*)</a>')



def counters2edges(counter_dict, p1_col, p2_col, w_col):
    edge = pd.DataFrame.from_records([
        (uid, feature, count)
        for uid, feature_counter in counter_dict.items()
        for feature, count in feature_counter.items()
    ], columns=[p1_col, p2_col, w_col])
    return edge



def prepare_content(in_fp, tqdm_desc="parse raw content", tqdm_total=None):
    user_features = defaultdict(lambda : defaultdict(Counter))
    for line in tqdm(in_fp, desc=tqdm_desc, total=tqdm_total):
        twt = json.loads(line)
        user_id = twt['user']['id_str_h']

        source = twt['source']
        source_match = SOURCE_REGEX.match(source)
        source_url = None
        if source_match:
            source_url = source_match.group(1)
            #source_follow = source_match.group(2)
            #source_text = source_match.group(3)
            if 'twitter.com' in source_url:
                source_url = None

        non_native = False
        if 'retweeted_status' in twt:
            non_native = True
            rtwt = twt['retweeted_status']

            retweeted_tweet_id = rtwt['id_str_h']
            user_features['retweet_tid'][user_id][retweeted_tweet_id] += 1

            if source_url is not None:
                user_features['retweet_source_url'][user_id][source_url] += 1
            #retweeted_user_id = rtwt['user']['id_str']
            #user_features['retweet_uid'][user_id][retweeted_user_id] += 1

        if 'quoted_status' in twt:
            non_native = True
            quoted_twt = twt['quoted_status']

            quoted_tweet_id = quoted_twt['id_str_h']
            user_features['quote_tid'][user_id][quoted_tweet_id] += 1

            if source_url is not None:
                user_features['quote_source_url'][user_id][source_url] += 1
            #quoted_user_id = quoted_twt['user']['id_str']
            #user_features['quote_uid'][user_id][quoted_user_id] += 1

        if 'in_reply_to_status_id_str_h' in twt:
            replied_tweet_id = twt['in_reply_to_status_id_str_h']
            if (replied_tweet_id is not None) and (len(replied_tweet_id) > 0):
                non_native = True
                user_features['reply_tid'][user_id][replied_tweet_id] += 1

                if source_url is not None:
                    user_features['reply_source_url'][user_id][source_url] += 1
                #replied_user_id = twt['in_reply_to_user_id_str_h']
                #user_features['reply_uid'][user_id][replied_user_id] += 1

        if non_native:
            continue

        if source_url is not None:
            user_features['native_source_url'][user_id][source_url] += 1
        #source_follow = source_match.group(2)
        #source_text = source_match.group(3)

        entities = twt['entities']

        #tags = [tag['text'].lower() for tag in entities['hashtags']]
        #user_features['hashtag'][user_id].update(tags)

        mentions = [ uid['id_str_h'] for uid in entities['user_mentions'] ]
        user_features['mention'][user_id].update(mentions)

        urls = list()
        for url in entities['urls']:
            expanded_url = url['expanded_url_h']

            if ('twitter.com' in expanded_url):
                continue

            if expanded_url.startswith('www.'):
                expanded_url = expanded_url[4:]
            urls.append(expanded_url)
        user_features['url'][user_id].update(urls)

    return user_features



def main(args):
    parser = argparse.ArgumentParser(
        description='parse raw tweet.json.gz files into feature parquets'
    )

    parser.add_argument('-i', '--infile',
        action="store", dest="infile", type=str, required=True,
        help="path to input parquet file of edge table")
    parser.add_argument('-o', '--outdir',
        action="store", dest="outdir", type=str, required=True,
        help="path to output directory for output randomized edge tables")
    parser.add_argument('-n', '--numline',
        action="store", dest="numline", type=int, required=True,
        help="number of lines in the input file")
    parser.add_argument('--p1col',
        action="store", dest="p1col", type=str, required=True,
        help="column name of nodes in partite 1")
    parser.add_argument('--p2col',
        action="store", dest="p2col", type=str, required=True,
        help="column name of nodes in partite 2")
    parser.add_argument('--wcol',
        action="store", dest="wcol", type=str, required=True,
        help="column name of edge weights")

    args = parser.parse_args(args)
    infile = args.infile
    outdir = args.outdir
    numline = args.numline
    p1_col = args.p1col
    p2_col = args.p2col
    w_col = args.wcol

    # read input
    with gzip.open(infile, 'rb') as in_fp:
        # do work
        user_features = prepare_content(in_fp, tqdm_total=numline)

    # write output
    for feature, counter_dict in user_features.items():
        edge_df = counters2edges(counter_dict, p1_col, p2_col, w_col)

        fname = "{}.edge.parquet".format(feature)
        edge_df.to_parquet(join(outdir, fname))



if __name__ == '__main__': main(sys.argv[1:])
