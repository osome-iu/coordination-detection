dataset = ['election_2020_09_25',
            'election_2020_11_03',
            'hunter_biden', 'voter_fraud',
            'hkp', 'argentina', 'debate',
            'covid', 'covid_fake_news',
            'hydroxychloroquine']
dataset_leitas = ['wh', 'pnd', 'venezuela']
dimension = [
    'retweet_tid', 'reply_tid', 'quote_tid',
    'retweet_source_url', 'reply_source_url', 'quote_source_url',
    'mention', 'native_source_url', 'url'
]

p1_col = 'uid'
p2_col = 'feature'
w_col = 'cnt'

interaction_n1_col = 'user1'
interaction_n2_col = 'user2'
interaction_sim_col = 'similarity'
interaction_sup_col = 'support'

num_sim = 200
sim_idx = list(range(num_sim))


#rule all:
#    input:
#        expand("features/{dataset}/{dimension}_simulations/{sim_idx}.edge.parquet",
#                dataset=dataset, dimension=dimension, sim_idx=sim_idx)

#rule all:
#    input:
#        expand("figures/{dataset}/{dimension}.coord.network.pdf",
#               dataset=dataset+dataset_leitas, dimension=dimension),
#        expand("features/{dataset}/table.by.user.pkl",
#               dataset=dataset+dataset_leitas)

rule all:
    input:
        expand("features/{dataset}/{dimension}.filtered.coord.graphml",
               dataset=dataset+dataset_leitas, dimension=dimension),
        expand("features/{dataset}/{dimension}.filtered.coord.pkl",
               dataset=dataset+dataset_leitas, dimension=dimension),
        expand("features/{dataset}/table.by.user.pkl",
               dataset=dataset+dataset_leitas)

#rule measure_p_values:
#    input:
#        infile="features/{dataset}/{dimension}.edge.parquet",
#        simfiles=expand("features/{{dataset}}/{{dimension}}_simulations/{sim_idx}.edge.parquet",
#                        sim_idx=sim_idx)
#    output:
#        "features/{dataset}/{dimension}.interactions.parquet"
#    params:
#        simdir="features/{dataset}/{dimension}_simulations"
#    shell:
#        """
#        python3 -m tcd.measure -i {input.infile} -s {params.simdir} -o {output} \
#                -n {num_sim} --p1col {p1_col} --p2col {p2_col} --wcol {w_col}
#        """

rule graph_tool_visualize:
    input:
        "features/{dataset}/{dimension}.filtered.coord.graphml"
    output:
        "figures/{dataset}/{dimension}.coord.network.pdf"
    shell:
        """
        python3 -m tcd.gtgraph -i {input} -o {output}
        """

rule combine_groups:
    input:
        interaction="features/{dataset}/{dimension}.interactions.parquet",
        tweettable="features/{dataset}/table.by.user.pkl"
    output:
        graph="features/{dataset}/{dimension}.filtered.coord.graphml",
        group="features/{dataset}/{dimension}.filtered.coord.pkl"
    shell:
        """
        python3 -m tcd.combine -i {input.interaction} -t {input.tweettable} \
                -o {output.graph} -g {output.group} \
                --node1 {interaction_n1_col} --node2 {interaction_n2_col} \
                --sim {interaction_sim_col} --sup {interaction_sup_col}
        """

rule measure_interaction:
    input:
        "features/{dataset}/{dimension}.edge.parquet"
    output:
        "features/{dataset}/{dimension}.interactions.parquet"
    shell:
        """
        python3 -m tcd.measure -i {input} -o {output} \
                --p1col {p1_col} --p2col {p2_col} --wcol {w_col} \
                --node1 {interaction_n1_col} --node2 {interaction_n2_col} \
                --sim {interaction_sim_col} --sup {interaction_sup_col}
        """

rule simulate_rewiring:
    input:
        infile="features/{dataset}/{dimension}.edge.parquet",
    output:
        expand("features/{{dataset}}/{{dimension}}_simulations/{sim_idx}.edge.parquet",
                sim_idx=sim_idx)
    params:
        outdir="features/{dataset}/{dimension}_simulations"
    shell:
        """
        python3 -m tcd.simulate -i {input.infile} -o {params.outdir} \
                -n {num_sim} --p1col {p1_col} --p2col {p2_col} --wcol {w_col}
        """

rule parse_json_to_tweet_tables:
    input:
        infile="data/{dataset}/raw_tweets.json.gz",
        numline="data/{dataset}/raw_tweets.numline",
    output:
        "features/{dataset}/table.by.user.pkl"
    run:
        if wildcards.dataset in dataset_leitas:
            shell("""
                python3 -m tcd.index_h -i {input.infile} -o {output} \
                        -n $(cat {input.numline})
            """)
        else:
            shell("""
                python3 -m tcd.index -i {input.infile} -o {output} \
                        -n $(cat {input.numline})
            """)

rule parse_json_to_edge_files:
    input:
        infile="data/{dataset}/raw_tweets.json.gz",
        numline="data/{dataset}/raw_tweets.numline",
    output:
        expand("features/{{dataset}}/{dimension}.edge.parquet", dimension=dimension)
    params:
        outdir="features/{dataset}"
    run:
        if wildcards.dataset in dataset_leitas:
            shell("""
                python3 -m tcd.parser_h -i {input.infile} -o {params.outdir} \
                        -n $(cat {input.numline}) \
                        --p1col {p1_col} --p2col {p2_col} --wcol {w_col}
            """)
        else:
            shell("""
                python3 -m tcd.parser -i {input.infile} -o {params.outdir} \
                        -n $(cat {input.numline}) \
                        --p1col {p1_col} --p2col {p2_col} --wcol {w_col}
            """)

rule count_raw_file_num_line:
    input:
        "data/{dataset}/raw_tweets.json.gz"
    output:
        "data/{dataset}/raw_tweets.numline"
    shell:
        "zcat {input} | wc -l > {output}"
