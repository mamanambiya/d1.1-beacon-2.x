"""
Viral SNP Endpoint.

* ``/genomic_snp_viral`` 

Query viral variants. 

.. note:: See ``schemas/genomic_query.json`` for checking the parameters accepted in this endpoint.
"""

import logging
import requests

from .exceptions import BeaconBadRequest, BeaconServerError, BeaconForbidden, BeaconUnauthorised
from .. import __apiVersion__, __id__
from ..conf.config import DB_SCHEMA

from ..utils.polyvalent_functions import create_prepstmt_variables

LOG = logging.getLogger(__name__)

def create_query(processed_request):
    """
    Restructure the request to build the query object
    """

    query = {
        "variant": {
            "referenceBases": processed_request.get("referenceBases", ""),
            "alternateBases": processed_request.get("alternateBases", ""),
            "referenceName": processed_request.get("referenceName", ""),
            "start": processed_request.get("start"),
            "end": processed_request.get("end"),
            "assemblyId": processed_request.get("assemblyId", "")
            },
        "datasets": {
            "datasetIds": '',
            "includeDatasetResponses": ''
             },
        "filters": ''
    }

    return query


def create_final_response(processed_request, results):
    """
    Create the final response as the Beacon Schema expects. 
    """

    # Create the query object to show it in the response
    query = create_query(processed_request)

    # We create the final dictionary with all the info we want to return
    beacon_response = {
                    "meta": {
                        "beaconId": __id__,
                        "apiVersion": __apiVersion__,
                        "receivedRequest": {
                            "meta": {
                                "requestedSchemas": {},
                                "apiVersion": __apiVersion__  # it is hardcoded because we only return v2 for this endpoint
                            },
                            "query": query
                        },
                        "returnedSchemas": {}
                    },
                    "value": {
                        'exists': any(results),
                        "error": None,
                        'results': results,
                        'info': None,
                        'resultsHandover': None,
                        'beaconHandover': [ { "handoverType" : {
                                                "id" : "CUSTOM",
                                                "label" : "Organization contact"
                                                },
                                                "note" : "Organization contact details maintaining this Beacon",
                                                "url" : "mailto:beacon.ega@crg.eu"
                                            } ]
                        
                        }
                    }

    return beacon_response


def transform_record(record):

    viralVariantObject =  {
        "variantBasic": {
            "ref_assembly_id": "-",
            "start_nucleotide": record.get('start'),
            "end_nucleotide": record.get('end'),
            "ref": record.get('reference'),
            "alt": record.get('alternate'),
        },
        "variantAnnotation": {
            "variant_id": "",  # external ref if it exists
            "variant_type": record.get('variant_type'),  # e.g “del”
            "variant_effect": "",  # e.g “miss-sense variant” 
            "genomic_region": "",  # categorical, from virus genomic annotation in VIRUS: annotation (SARS-CoV2: 5UTR,ORF1ab, S, ORF3a, Intergenic, E,M, ORF6, ORF7a, ORF8, N, ORF10, 3UTR)
            "functional_region": "",  # categorical, from functional annotation file VIRUS: annotation e.g “HVR”, “RBD”, “RNA modification site”
        },
        "variantInSample": {
            "variant_file_id": "",  # external ref -or internal if we run pipeline
            "variant_frequency_dataset": float(record.get('frequency')),  # from vcf
            "info": {
                "biosample_id": record.get("sample_id"),  # (external ref ) e.g "SRS6007144"
                "host_id": "",  # (external ref if it exists)
                "study_info": {
                    "study_id": "",  # (study accession): e.g  "SRP242226"
                    "study_ref": "",  # (article PUBMED ID or URL)
                },
                "experiment_info": {
                    "sequence_file_id": "",  # (run accession) e.g "SRR10903401"
                    "exp_id": "",  # (experiment accession): e.g  "SRX7571571"
                    "exp_title": "",  # e.g ”Total RNA sequencing of BALF (human reads removed)”
                    "exp_lib_strategy": "",  # (“RNA-Seq”, “WGS”, “AMPLICON”, “Targeted-Capture”) 
                    "exp_lib_source": "",  # (“METATRANSCRIPTOMIC”, “METAGENOMIC”, “GENOMIC” , “VIRAL RNA”)
                    "exp_lib_selection": "",  # ( “RANDOM”, “RT-PCR”, “RANDOM PCR”, “unspecified”, “PCR”, “cDNA”)
                    "exp_lib_layout": "",  # (“PAIRED” “SINGLE”) 
                    "exp_platform": "",  # (“Illumina , “Nanopore”)
                    "exp_platform_model": "",  # (“Illumina MiSeq”, “Illumina MiniSeq” , ”Illumina HiSeq 2500” ,”NextSeq 500” , ”NextSeq 550”, “Illumina iSeq 100”, "GridION" ) 
                    "variant_caller": "",
                }
            }
        },
        "biosample": {
            "collection_date": "",  # e.g  "2020-02-14" 
            "biosample_type": "",  # (sample type/source) e.g "Bronchoalveolar lavage fluid” or “Cellular passage”
            "procedure": {
                "culture_cell": "",  # e.g: "Vero E6 cells (CRL-1586)" (NULL or none if not culture)
                "culture_passage_history": "",  # e.g "Original (not passaged)" (NULL or none if not culture)
                "biosample_id": "",  # (external ref ) e.g "SRS6007144"
                "biosample_alt_id": "",  # (external ref ) e.g "SAMN13872787"
                "biosample_ref_material": "",  # e.g "BEI Resources catalog NR-52281 (lot 70033135)
            }
        },
        "individual": {
            "host_taxon_id": "",  # e.g "9606" (“Homo sapiens”)
            "host_age": "",  # e.g “21”  (age in default schema)
            "host_sex": "",  # “female”, “male” (sex in default schema)
            "geo_origin": "",  # e.g "USA:WI:Madison”
            "disease": "",  # (relevant virus-related diseases) e.g "pneumonia”
            "disease_stage": "",  # e.g “acute”
            "comorbidities": "",  # (underlying chronic diseases, format as individualDiseases from default schema): e.g ICD10 for “diabetes mellitus type II”
            "disease_course": "",  # categorical “asymptomatic”, ”mild”, “severe” 
            "disease_outcome": "",  # e.g ”resolution/discharge” , “fatal”
            "info": {
                "individual_id": ""  # (external ref ) 
            }
        },
        "virus": {
            "taxon_id": "",  # e.g ”433733”
            "taxon_name": "",  # e.g “Severe acute respiratory syndrome coronavirus 2”
            "strain_id": "",
            "strain_name": "",  # e.g "2019-nCoV/USA-WI1/2020" 
            "annotation": {
                "genomic_annotation": "",  # file url
                "functional_annotation": ""  # file url
            }
        }
    }
    return viralVariantObject

async def fetch_from_db(db_pool, query_parameters):
    """
    """
    async with db_pool.acquire(timeout=180) as connection:
        results = []
        try: 
            query = f"""SELECT * FROM {DB_SCHEMA}.query_data_response_viral({create_prepstmt_variables(13)});"""
            LOG.debug(f"QUERY to fetch hits: {query}")
            statement = await connection.prepare(query)
            db_response = await statement.fetch(*query_parameters)         

            for record in list(db_response):
                processed = transform_record(record)
                results.append(processed)
            return results
        except Exception as e:
                raise BeaconServerError(f'Query resulting datasets DB error: {e}') 


def request2queryparameters(processed_request):
    """
    Reorganize the request to match the query_summary_response() SQL function input.
    """
    # We create a list of the parameters that the SQL function needs
    correct_parameters =  [
	"variantType",
	"start",
	"startMin",
	"startMax",
	"end",
	"endMin",
	"endMax",
	"referenceName",
	"referenceBases",
	"alternateBases",
	"assemblyId",
	"datasetIds",
    "filters"]
    
    int_params = ['start', 'end', 'endMax', 'endMin', 'startMax', 'startMin']

    query_parameters = []

    # Iterate correct_parameters to create the query_parameters list from the processed_request 
    # in the required order and with the right types
    for param in correct_parameters:
        query_param = processed_request.get(param)
        if query_param:
            if param in int_params:
                query_parameters.append(int(query_param))
            else:
                query_parameters.append(str(query_param))
        else:
            if param in int_params:
                query_parameters.append(None)
            else:
                query_parameters.append("null")


    # At this point we have a list with the needed parameters called query_parameters, the only thing 
    # laking is to update the datasetsIds (it can be "null" or processed_request.get("datasetIds"))

    LOG.debug(f"Correct param: {correct_parameters}")
    LOG.debug(f"Query param: {query_parameters}")
    LOG.debug(f"Query param types: {[type(x) for x in query_parameters]}")

    return query_parameters


#### HANDLER

async def viral_snp_handler(request, processed_request, db_pool):
    """"""
    # 1. PARSE THE REQUEST to prepare it to be used in the SQL function
    LOG.info('Parsing request.')
    processed_request['datasetIds'] = '1'
    query_parameters = request2queryparameters(processed_request)
    LOG.info('Parsing request done.')

    # 2. RETRIEVE DATA FROM THE DB (use SQL function)
    LOG.info('Connecting to the DB to make the query.')
    results = await fetch_from_db(db_pool, query_parameters)
    LOG.info('Query done.')

    # 3. SHAPE FINAL RESPONSE
    LOG.info('Creating the final response.')
    beacon_response = create_final_response(processed_request, results)
    LOG.info('Done.')

    return beacon_response
