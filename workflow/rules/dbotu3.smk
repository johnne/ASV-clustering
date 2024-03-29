localrules:
    dbotu3,
    dbotu32tab,


rule run_dbotu3:
    """
    dbotu3 requires that all sequences in the fasta are also in the counts table
    and vice versa. However there's no requirement that total counts for 
    sequences are > 0
    """
    input:
        fasta=rules.filter_seqs.output.fasta,
        counts=rules.filter_seqs.output.counts,
    output:
        tsv="results/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}/dbotu3.tsv",
        memb="results/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxxa/{tax}/{run_name}/dbotu3.clusters.tsv",
    log:
        log="logs/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}/dbotu3.log",
        err="logs/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}/dbotu3.err",
    params:
        dist=config["dbotu3"]["dist"],
        abund=config["dbotu3"]["abund"],
        pval=config["dbotu3"]["pval"],
        tmpdir="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/{tax}",
        fasta="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/{tax}/asv_seqs.fasta",
        counts="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/{tax}/asv_counts.tsv",
        tsv="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/{tax}/dbotu3.tsv",
        memb="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/{tax}/dbotu3.clusters.tsv",
    conda:
        "../envs/dbotu3.yml"
    resources:
        runtime=60 * 24,
        mem_mb=mem_allowed,
    shell:
        """
        mkdir -p {params.tmpdir}
        gunzip -c {input.fasta} > {params.fasta}
        gunzip -c {input.counts} > {params.counts}
        dbotu3.py -d {params.dist} -a {params.abund} -p {params.pval} \
            {params.counts} {params.fasta} -o {params.tsv} --membership {params.memb} --log {log.log} 2> {log.err}
        mv {params.tsv} {output.tsv}
        mv {params.memb} {output.memb}
        rm -rf {params.tmpdir}
        """


rule dbotu32tab:
    input:
        rules.run_dbotu3.output.memb,
    output:
        "results/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}/asv_clusters.tsv",
    params:
        tmpdir="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}",
        out="$TMPDIR/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}/asv_clusters.tsv",
    script:
        "../scripts/dbotu3_utils.py"


rule dbotu3:
    input:
        expand(
            "results/dbotu3/{rundir}/{chimera_run}/{chimdir}/{rank}/taxa/{tax}/{run_name}/asv_clusters.tsv",
            rundir=config["rundir"],
            chimera_run=config["chimera"]["run_name"],
            chimdir=config["chimdir"],
            rank=config["split_rank"],
            tax=taxa,
            run_name=config["run_name"],
        ),
