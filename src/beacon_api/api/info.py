"""
Info Endpoint.

Querying the info endpoint reveals information about this beacon and its existing datasets 
and their associated metadata.

* ``/`` Beacon-v1
* ``/info`` Beacon-v1
* ``/info?model=GA4GH-ServiceInfo-v0.1`` GA4GH
* ``/service-info`` GA4GH

.. note:: See ``beacon_api`` root folder ``__init__.py``  and  ``/utils/models.py`` for changing values used here.
"""

import logging

from .. import __id__, __beacon_name__, __apiVersion__, __org_id__, __org_name__, __org_description__, __org_adress__, __org_welcomeUrl__, __org_contactUrl__, __org_logoUrl__, __org_info__
from .. import __description__, __version__, __welcomeUrl__, __alternativeUrl__, __createDateTime__, __updateDateTime__
from .. import __cohorts_json__
from .exceptions import BeaconBadRequest, BeaconServerError, BeaconBasicBadRequest

from ..utils.models import GA4GH_ServiceInfo_v01, Beacon_v1, organization, sample_allele_request

from ..utils.polyvalent_functions import filter_response
from .access_levels import ACCESS_LEVELS_DICT
from ..utils.translate2accesslevels import info2access

LOG = logging.getLogger(__name__)


# ----------------------------------------------------------------------------------------------------------------------
#                                         FORMATTING
# ----------------------------------------------------------------------------------------------------------------------

def transform_metadata(record):
    """Format the metadata record we got from the database to adhere to the response schema."""
    response = dict(record)

    response["id"] = response.pop("datasetId")  
    response["name"] = None
    response["description"] = response.pop("description")
    response["assemblyId"] = response.pop("assemblyId")  
    response["createDateTime"] = None 
    response["updateDateTime"] = None
    response["dataUseConditions"] = None
    response["version"] = None
    response["variantCount"] = 0 if response.get("variantCount") is None else response.get("variantCount")
    response["callCount"] = 0 if response.get("callCount") is None else response.get("callCount")
    response["sampleCount"] = 0 if response.get("sampleCount") is None else response.get("sampleCount")
    response["externalURL"] = None
    response["info"] = {"accessType": response.get("accessType"),
                        "authorized": 'true' if response.pop("accessType") == "PUBLIC" else 'false'}  

    return response


# ----------------------------------------------------------------------------------------------------------------------
#                                         MAIN QUERY TO THE DATABASE
# ----------------------------------------------------------------------------------------------------------------------

async def fetch_dataset_metadata(db_pool, datasets=None, access_type=None):
    """
    Execute query for returning dataset metadata.

    Returns a list of datasets metadata dictionaries. 
    """
    # Take one connection from the database pool
    async with db_pool.acquire(timeout=180) as connection:
        # Start a new session with the connection
        async with connection.transaction():
            # Fetch dataset metadata according to user request
            datasets_query = None if not datasets else datasets
            access_query = None if not access_type else access_type
            try:

                query = """SELECT stable_id as "datasetId", description as "description", access_type as "accessType",
                           reference_genome as "assemblyId", variant_cnt as "variantCount",
                           call_cnt as "callCount", sample_cnt as "sampleCount"
                           FROM beacon_dataset WHERE
                           coalesce(stable_id = any($1::varchar[]), true)
                           AND coalesce(access_type = any($2::varchar[]), true);
                           """
                statement = await connection.prepare(query)
                db_response = await statement.fetch(datasets_query, access_query)
                metadata = []
                LOG.info(f"Showing the INFO endpoint.")
                for record in list(db_response):
                    metadata.append(transform_metadata(record))
                return metadata
            except Exception as e:
                raise BeaconServerError(f'Query metadata DB error: {e}')


# ----------------------------------------------------------------------------------------------------------------------
#                                         HANDLER FUNCTION
# ----------------------------------------------------------------------------------------------------------------------

async def info_handler(request, processed_request, pool, info_endpoint=False, service_info=False):
    """
    Construct the `Beacon` app information dict.
    Handle in which model the info is output depending on the endpoint and the parameters passed. 

    :info_rendpoint: boolean to decide which response model to use.
    :service_info: boolean to decide which response model to use.

    Returns the beacon response dictionary. 
    """

    # Fetch the info about the datasets
    beacon_dataset = await fetch_dataset_metadata(pool)

    # Decide whether the Beacon_v1 or the GA4GH spec is used (while validating the model parameter)
    # if info, then check the parameter model, if it is passed fine then use GA4GH model, if not, use the default model, which is Beacon-v1
    if info_endpoint:
        if not processed_request:
            LOG.info('Using Beacon API Specification format for Service Info.')
            beacon_info = Beacon_v1(request.host)
        elif processed_request.get("model") and processed_request.get("model") == 'GA4GH-ServiceInfo-v0.1':
            LOG.info('Using GA4GH Discovery format for Service Info.')
            beacon_info = GA4GH_ServiceInfo_v01(request.host)
        else:
            error = "The info endpoint only accepts 'model' as parameter with 'GA4GH-ServiceInfo-v0.1' as value."
            raise BeaconBasicBadRequest(processed_request, request.host, error)
    # if there is service_info then use ga4gh
    elif service_info:
        LOG.info('Using GA4GH Discovery format for Service Info.')
        beacon_info = GA4GH_ServiceInfo_v01(request.host)
    # if there is no info, the default model
    else:
        LOG.info('Using Beacon API Specification format for Service Info.')
        beacon_info = Beacon_v1(request.host)

    beacon_info.update({'datasets': beacon_dataset,
                        # If one sets up a beacon it is recommended to adjust these sample requests
                        'sampleAlleleRequests': sample_allele_request}) 

    if __cohorts_json__:
        beacon_info.update({'cohorts': __cohorts_json__})

    # Before returning the response we need to filter it depending on the access levels
    beacon_response = {"beacon": beacon_info}
    accessible_datasets = []  # NOTE we use the an empty list because in this endpoint we don't filter by dataset
    user_levels = ["PUBLIC"]  # NOTE we hardcode it because authentication is not implemented yet
    filtered_response = filter_response(beacon_response, ACCESS_LEVELS_DICT, accessible_datasets, user_levels, info2access)

    return filtered_response["beacon"]

    # return beacon_info


# ----------------------------------------------------------------------------------------------------------------------
#                                         COHORTS HANDLER FUNCTION
# ----------------------------------------------------------------------------------------------------------------------

async def cohorts_handler(request, processed_request):
    """
    Construct the `Beacon` cohort information dict.

    Returns the cohort response dictionary. 
    """

    ncohorts = 0
    cohorts_as_list = []
    if __cohorts_json__:
        if isinstance(__cohorts_json__, list):
            ncohorts = len(__cohorts_json__)
            cohorts_as_list = __cohorts_json__
        else:
            ncohorts = 1
            cohorts_as_list = [ __cohorts_json__ ]

    response = {
                "meta": {
                    "beaconId": __id__,
                    "apiVersion": "v2.0.0-draft.1",
                    "receivedRequest": {
                        "meta": {
                            "requestedSchemas": {},
                            "apiVersion": ""
                        },
                        "query": {}
                    },
                    "returnedSchemas": {
                        "Cohort": ["beacon-cohort-v0.1"]*ncohorts
                    }
                }}

    cohorts_response = {
        "exists": False,
        "info": "",
        "resultsHandover": "",
        "beaconHandover": ""
    }

    if ncohorts > 0:
        cohorts_response['exists'] = True
        cohorts_response['results'] = []
        for cohort in cohorts_as_list:
            cohorts_response['results'].append({
                "defaultSchema": {
                    "version": "beacon-cohort-v0.1",
                    "value": cohort
                },
                "alternativeSchemas": []
            })

    response["response"] = cohorts_response
    return response
