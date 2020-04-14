-- Load data about datasets
INSERT INTO beacon_dataset_table(id, stable_id, description, access_type, reference_genome, variant_cnt, call_cnt, sample_cnt)  
  VALUES (1, 'coronavirus-testdata', 'Variants of 61 Coronavirus.', 'PUBLIC', '-', 1, 1, 1);

-- Init dataset-ConsentCodes table
INSERT INTO beacon_dataset_consent_code_table (dataset_id, consent_code_id , additional_constraint, version) 
  VALUES(1, 1, null, 'v1.0'); -- NRES - No restrictions on data use

-- Load data for the access_levels endpoint
INSERT INTO public.dataset_access_level_table (dataset_id, parent_field, field, access_level) VALUES (1, 'accessLevelSummary', '-', 'PUBLIC');
