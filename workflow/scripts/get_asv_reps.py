#!/usr/bin/env python

from argparse import ArgumentParser
import pandas as pd
import numpy as np
import gzip as gz
import sys
from os.path import splitext
from Bio.SeqIO import parse
import tqdm
from subprocess import check_output


def normalize_row(vals, header, colsums):
    return [
        float(vals[i]) / float(colsums.loc[header[i]])
        if colsums.loc[header[i]].values[0] > 0
        else 0
        for i in list(range(0, len(vals)))
    ]


def check_lines(f):
    if f.endswith(".gz"):
        return None
    command = ["wc", "-l", f]
    l = check_output(command)
    lines = int(l.decode().lstrip(" ").split(" ")[0]) - 1
    return lines


def read_counts(f, method, ids, colsums=None):
    lines = check_lines(f)
    if method == "sum":
        func = np.sum
    elif method == "median":
        func = np.median
    elif method == "mean":
        func = np.mean
    d = {}
    if f.endswith(".gz"):
        open_func = gz.open
    else:
        open_func = open
    with open_func(f, "rt") as fhin:
        for i, line in enumerate(tqdm.tqdm(fhin, unit=" lines", ncols=50, total=lines)):
            line = line.rstrip()
            items = line.split("\t")
            if i == 0:
                header = items[1:]
                continue
            asv = items[0]
            if asv not in ids:
                continue
            vals = [int(x) for x in items[1:]]
            if colsums is not None:
                vals = normalize_row(vals, header, colsums)
            v = func(vals)
            d[asv] = v
    return pd.DataFrame(d, index=[method]).T


def get_reps(df, method, rank):
    reps = pd.DataFrame()
    for rank_name in tqdm.tqdm(
        df[rank].unique(), unit=" taxa", total=len(df[rank].unique()), ncols=50
    ):
        rows = df.loc[df[rank] == rank_name]
        _reps = rows.loc[rows[method] == rows.max()[method]].head(1)
        reps = pd.concat([reps, _reps])
    return reps


def filter_taxa(taxa, rank):
    filtered = taxa.loc[
        ~(taxa[rank].str.startswith("unclassified"))
        & ~(taxa[rank].str.contains("_[X]+$"))
    ]
    return filtered


def get_seqs(seqsfile, reps, ranks, rank):
    seqs = {}
    for record in tqdm.tqdm(parse(seqsfile, "fasta"), unit=" records", ncols=50):
        try:
            row = reps.loc[record.id]
        except KeyError:
            continue
        rank_name = row[rank]
        lineage = ";".join([x for x in row.loc[ranks]])
        desc = f"{lineage}"
        header = f">{record.id} {desc}"
        if rank_name not in seqs.keys():
            seqs[rank_name] = {"recid": header, "seq": record.seq}
        else:
            if len(record.seq) > len(seqs[rank_name]["seq"]):
                seqs[rank_name] = {"recid": header, "seq": record.seq}
    return seqs


def write_seqs(seqs, outfile):
    if not outfile:
        w = sys.stdout
    else:
        w = open(outfile, "w")
    with w as fhout:
        for seqid, d in seqs.items():
            fhout.write(f"{d['recid']}\n{d['seq']}\n")


def calc_colsum(f):
    colsums = []
    data = pd.read_csv(f, sep="\t", index_col=0, chunksize=100000)
    for item in tqdm.tqdm(
        data, unit=" chunks", ncols=50, desc="Reading counts file in chunks"
    ):
        colsums.append(item.sum(axis=0))
    return sum(colsums)


def main(args):
    sys.stderr.write(f"Reading taxfile {args.taxa}\n")
    taxa = pd.read_csv(args.taxa, index_col=0, sep="\t")
    if args.prefix:
        taxa[args.rank] = [f"{args.prefix}_{x}" for x in taxa[args.rank]]
    sys.stderr.write(f"Read {taxa.shape[0]} records\n")
    taxa.index.name = "ASV"
    ranks = list(taxa.columns)
    if args.no_unclassified:
        sys.stderr.write(f"Filtering taxonomy to remove unassigned\n")
        filtered = filter_taxa(taxa, args.rank)
        sys.stderr.write(f"{filtered.shape[0]} records remaining\n")
    else:
        filtered = taxa
    colsums = None
    if args.normalize:
        if args.colsums:
            sys.stderr.write(f"Reading column sums from {args.colsums}\n")
            colsums = pd.read_csv(args.colsums, sep="\t", index_col=0)
        else:
            sys.stderr.write(f"Calculating column sums for normalization\n")
            colsums = calc_colsum(args.counts)
    sys.stderr.write(
        f"Reading countsfile {args.counts} and calculating abundance of ASVs using {args.method} across samples\n"
    )
    counts = read_counts(args.counts, args.method, list(filtered.index), colsums)
    counts.index.name = "ASV"
    dataframe = pd.merge(filtered, counts, left_index=True, right_index=True)
    sys.stderr.write(f"Finding representatives for rank {args.rank}\n")
    reps = get_reps(dataframe, args.method, args.rank)
    rep_size = reps.groupby(args.rank).size()
    sys.stderr.write(
        f"{rep_size.loc[rep_size>1].shape[0]} {args.rank} reps with >1 ASV\n"
    )
    if args.taxa_table:
        sys.stderr.write(f"Adding additional taxonomic info from {args.taxa_table}\n")
        extra_taxdf = pd.read_csv(args.taxa_table, sep="\t", index_col=0)
        taxdf = pd.merge(dataframe, extra_taxdf, left_index=True, right_index=True)
        taxdf = taxdf.assign(
            representative=pd.Series([0] * taxdf.shape[0], index=taxdf.index)
        )
        taxdf.loc[reps.index, "representative"] = 1
        taxaout = f"{splitext(args.outfile)[0]}.taxonomy.tsv"
        taxdf.to_csv(taxaout, sep="\t")
    sys.stderr.write(f"Reading sequences from {args.seqs}\n")
    seqs = get_seqs(args.seqs, reps, ranks, args.rank)
    write_seqs(seqs, args.outfile)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("taxa", type=str, help="Taxonomic assignments")
    parser.add_argument(
        "counts", type=str, help="Counts of ASVs (rows) in samples (columns)"
    )
    parser.add_argument("seqs", type=str, help="Sequence file for ASVs")
    parser.add_argument(
        "outfile",
        type=str,
        help="Write representatives to outfile",
    )
    parser.add_argument(
        "--rank", type=str, default="BOLD_bin", help="What level o group TAX ids"
    )
    parser.add_argument("--prefix", type=str, help="Prefix cluster name with string")
    parser.add_argument(
        "--method",
        type=str,
        choices=["sum", "median", "mean"],
        default="median",
        help="Method to select representative base on counts. Defaults to 'sum' across samples",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize counts before applying method",
    )
    parser.add_argument(
        "--colsums",
        type=str,
        help="File with pre-calculated read count sums for samples",
    )
    parser.add_argument(
        "--no-unclassified",
        action="store_true",
        help="Remove ASVs marked as 'unclassified' or suffixed with '_X'",
    )
    parser.add_argument(
        "--taxa-table",
        type=str,
        help="Additional taxonomy table to merge representatives with",
    )
    args = parser.parse_args()
    main(args)
