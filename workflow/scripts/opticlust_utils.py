#!/usr/bin/env python

import pandas as pd
import os
import shutil


def get_cluster_members(df):
    df.drop("numOtus", axis=1, inplace=True)
    d = {}
    for cutoff in df.index:
        d[cutoff] = {}
        dataf = df.loc[cutoff]
        # Skip empty
        dataf = dataf.loc[dataf == dataf]
        for otu in dataf.index:
            asv_ids = dataf.loc[otu].split(",")
            for asv_id in asv_ids:
                d[cutoff][asv_id] = otu
    dataf = pd.DataFrame(d)
    return dataf


def opticlust2tab(sm):
    """
    Transform opticlust cluster membership file (*.list) to a table
    that is easier to work with
    """
    df = pd.read_csv(sm.input[0], sep="\t", index_col=0, header=0)
    dataf = get_cluster_members(df)
    os.makedirs(sm.params.tmpdir, exist_ok=True)
    dataf.to_csv(sm.params.out, sep="\t")
    shutil.move(sm.params.out, sm.output[0])
    os.removedirs(sm.params.tmpdir)


def reformat_distmat(sm):
    """
    Reformat vsearch output from:
    7d19d222ca1e44c604b6e48b990bbf10        9a0a36461e4a54d0b778c04b6a29cb64        99.3
    7d19d222ca1e44c604b6e48b990bbf10        568cdc839eb96fa92af785d50175d384        98.6
    7d19d222ca1e44c604b6e48b990bbf10        7a9c36e07857d49372c0674eaeba44b6        98.6

    to
    7d19d222ca1e44c604b6e48b990bbf10        9a0a36461e4a54d0b778c04b6a29cb64        0.007
    7d19d222ca1e44c604b6e48b990bbf10        568cdc839eb96fa92af785d50175d384        0.014
    7d19d222ca1e44c604b6e48b990bbf10        7a9c36e07857d49372c0674eaeba44b6        0.014

    """
    import gzip as gz
    os.makedirs(sm.params.tmpdir, exist_ok=True)
    with gz.open(sm.input[0], 'rt') as fhin, gz.open(sm.params.out,
                                                     'wt') as fhout:
        for line in fhin:
            line = line.rstrip()
            asv1, asv2, p = line.split("\t")
            fhout.write(f"{asv1}\t{asv2}\t{(100 - float(p)) / 100}\n")
    shutil.move(sm.params.out, sm.output[0])
    os.removedirs(sm.params.tmpdir)


def main(sm):
    toolbox = {'reformat_distmat': reformat_distmat,
               'opticlust2tab': opticlust2tab}
    toolbox[sm.rule](sm)


if __name__ == '__main__':
    main(snakemake)
