#!/usr/bin/env bash

echo "Loading initial data into the beacon database"

# Move to the script directory
pushd $(dirname ${BASH_SOURCE[0]})

# Note: we hide the .sql files inside data/ so that the entrypoint does not pick them up
# and execute them. We are doing it ourselves.
# But we do want to run the .sh file

# Using docker_process_sql() from the /docker-entrypoint-initdb.d
# This file will be sourced because it is not executable
# See (for postgres 9.6-alpine):
# https://github.com/docker-library/postgres/blob/34df4665bfdccf28deac2ed2924127b94489a576/9.6/alpine/docker-entrypoint.sh#L139-L145

# Schemas and Functions
docker_process_sql < data/schemas.sql
docker_process_sql < data/query_data_summary_response.sql
docker_process_sql < data/query_data_response.sql
docker_process_sql < data/query_data_response_viral.sql

docker_process_sql -c "GRANT EXECUTE ON FUNCTION public.query_data_summary_response(text, integer, integer, integer, integer, integer, integer, character varying, text, text, text, text, text) TO ${POSTGRES_USER};"
docker_process_sql -c "GRANT EXECUTE ON FUNCTION public.query_data_response(text, integer, integer, integer, integer, integer, integer, character varying, text, text, text, text, text) TO ${POSTGRES_USER};"

# Datasets
docker_process_sql < data/init.sql


# ----------------------------------------
#            VIRAL BEACON DATA
# ----------------------------------------
echo Inserting viral data
# 1. Remember to modify the init.sql

# 2. Load the variants
docker_process_sql -c \
    "copy beacon_data_table (dataset_id,chromosome,start,variant_id,reference,alternate,\"end\",\"type\",sv_length,variant_cnt,call_cnt,sample_cnt,frequency,matching_sample_cnt) from stdin using delimiters ';' csv" < data/Viral61.vcf.gz.variants_v2.data
echo "> Variants done"

# 3. Load the samples
docker_process_sql -c \
"copy tmp_sample_table (sample_stable_id,dataset_id) from stdin using delimiters ';' csv" < data/Viral61.vcf.gz.samples_v2.data
echo "> Samples done"

# 4. Load the samples matching variants
docker_process_sql -c \
"copy tmp_data_sample_table (dataset_id,chromosome,start,variant_id,reference,alternate,\"type\",sample_ids) from stdin using delimiters ';' csv" < data/Viral61.vcf.gz.variants.matching.samples_v2.data
echo "> Variants-samples done"

echo Done inserting viral data
# ----------------------------------------
#        END VIRAL BEACON DATA
# ----------------------------------------


docker_process_sql -c "INSERT INTO beacon_sample_table (stable_id)
         SELECT DISTINCT t.sample_stable_id
         FROM tmp_sample_table t
         LEFT JOIN beacon_sample_table sam ON sam.stable_id=t.sample_stable_id
         WHERE sam.id IS NULL"

docker_process_sql -c "INSERT INTO beacon_dataset_sample_table (dataset_id, sample_id)
         SELECT DISTINCT dat.id AS dataset_id, sam.id AS sample_id
         FROM tmp_sample_table t
         INNER JOIN beacon_sample_table sam ON sam.stable_id=t.sample_stable_id
         INNER JOIN beacon_dataset_table dat ON dat.id=t.dataset_id
         LEFT JOIN beacon_dataset_sample_table dat_sam ON dat_sam.dataset_id=dat.id AND dat_sam.sample_id=sam.id
         WHERE dat_sam.id IS NULL"

# Finally
docker_process_sql -c "INSERT INTO beacon_data_sample_table (data_id, sample_id)
         SELECT data_sam_unnested.data_id, s.id AS sample_id
         FROM (
             SELECT dt.id as data_id, unnest(t.sample_ids) AS sample_stable_id
             FROM tmp_data_sample_table t
             INNER JOIN beacon_data_table dt ON dt.dataset_id=t.dataset_id
                                            AND dt.chromosome=t.chromosome
					    AND dt.variant_id=t.variant_id
					    AND dt.reference=t.reference
					    AND dt.alternate=t.alternate
					    AND dt.start=t.start
					    AND dt.type=t.type 
         )data_sam_unnested
         INNER JOIN beacon_sample_table s ON s.stable_id=data_sam_unnested.sample_stable_id
         LEFT JOIN beacon_data_sample_table ds ON ds.data_id=data_sam_unnested.data_id AND ds.sample_id=s.id
         WHERE ds.data_id IS NULL"

docker_process_sql -c "TRUNCATE TABLE tmp_sample_table"
docker_process_sql -c "TRUNCATE TABLE tmp_data_sample_table"

popd 
echo "Initial data loaded"
