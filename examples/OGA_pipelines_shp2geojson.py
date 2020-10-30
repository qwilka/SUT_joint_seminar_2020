"""
Convert UK OGA offshore pipelines shapefile data into geojson.

References:
https://data-ogauthority.opendata.arcgis.com/datasets/oga-offshore-zipped-shapefiles-wgs84  OGA_OFF_WGS84.zip
https://ndr.ogauthority.co.uk   DealPipelinesKis.csv


"""
from datetime import datetime
import json
import os
import subprocess
from zipfile import ZipFile

from dateutil import parser as duparser
import geopandas
import numpy as np
import pandas as pd


# Inputs ----------
# https://ndr.ogauthority.co.uk
# More>Infrastructure>Pipelines
# click "Export->" button and "Export all data" to CSV file
NDR_pipelines_fname = "/home/develop/engineering/data/UK/OGA/NDR_National_Data_Repository/2020-07-27_data_download/DealPipelinesKis.csv"

# https://data-ogauthority.opendata.arcgis.com/datasets/oga-offshore-zipped-shapefiles-wgs84
OGA_zip_fname = "OGA_OFF_WGS84.zip"
shp_stem_name = "OGA_Pipelines_WGS84"   # specify the root name of the shape file, no extension

geojson_fname = "OGA_pipelines.geojson"  # output file name

# clean-up extracted/temporary files
cleanup = True
# use geopandas to create geojson (direct_method=True), or use alternative method (False)
direct_method = True 
# minify geojson file (requires https://github.com/TNOCS/minify-geojson)
minify_geojson = True
# End inputs --------


DealPipelines_df = pd.read_csv(NDR_pipelines_fname)

# extract shape files from OGA_OFF_WGS84.zip
extracted_files = []
with ZipFile(OGA_zip_fname, 'r') as zf:
    zfiles = zf.namelist()
    for _fname in zfiles:
        if not _fname.startswith(shp_stem_name):
            continue
        op = zf.extract(_fname)
        if op.lower().endswith(".shp"):
            shp_fname = op
        extracted_files.append(op)

OGA_pl_df = geopandas.read_file(shp_fname) 

# clean up...
if cleanup:
    for _fname in extracted_files:
        os.remove(_fname)
        print(f"INFO: deleted shape file {os.path.basename(_fname)}")


if direct_method:
    OGA_pl_df.to_file(geojson_fname, driver='GeoJSON')
    with open(geojson_fname, 'r') as fh:
        OGA_pl_data = json.load(fh)
else:
    # alternative/indirect way to create geojson from geopandas dataframe
    print(f"INFO: using indirect method to create geojson")
    OGA_pl_data = OGA_pl_df.to_json() # alternative way to create geojson from geopandas dataframe
    OGA_pl_data = json.loads( OGA_pl_data )


# filter the properties object in each geojson feature to retain only relevant metadata
for _f in OGA_pl_data['features']:
    _meta = {k:v for k,v in _f['properties'].items() if v is not None} #_f['properties'].copy()
    _id = _f['properties']['ID']
    _dealpl = DealPipelines_df.loc[DealPipelines_df['PIPELINEID'] == _id]
    if not _dealpl.empty:
        dd = _dealpl.iloc[0].to_dict()
        dd = {k:v for k,v in dd.items() if pd.notna(v) and str(v).strip() != "" }
        _meta.update(dd)

    new_meta = {}
    if 'PIPELINE_NAME' in _meta:
        new_meta["name"] = _meta['PIPELINE_NAME']
    elif 'PIPE_NAME' in _meta:
        new_meta["name"] = _meta['PIPE_NAME']
    elif 'PIPELINE_STDNAME' in _meta:
        new_meta["name"] = _meta['PIPELINE_STDNAME']
        
    if 'OPERATOR' in _meta:
        new_meta["operator"] = _meta['OPERATOR']
    elif 'PIPE_NAME' in _meta:
        new_meta["operator"] = _meta['NAMING_COMPANY']  

    if 'PIPELINE_DTINO' in _meta:
        new_meta["ID"] = _meta['PIPELINE_DTINO']
    elif 'PIPE_DTINO' in _meta:
        new_meta["ID"] = _meta['PIPE_DTINO']

    if 'DESCRIPTION' in _meta:
        new_meta["desc"] = _meta['DESCRIPTION']
    elif 'DESC_' in _meta:
        new_meta["desc"] = _meta['DESC_']

    #if 'ID' in _meta:
    #    new_meta["OGA_db_id"] = _meta['ID']
    #elif 'PIPELINEID' in _meta:
    #    new_meta["OGA_db_id"] = _meta['PIPELINEID']
    #elif 'EntityKey' in _meta:
    #    new_meta["OGA_db_id"] = _meta['EntityKey']

    if 'START_DATE' in _meta:
        new_meta["startup"] = duparser.parse(_meta['START_DATE']).date().isoformat()

    if 'PIPELINE_LENGTH_M' in _meta:
        length = float(_meta['PIPELINE_LENGTH_M'])
        if length<1000:
            new_meta["length"] = "{:d} m".format(round(length))
        else:
            new_meta["length"] = "{:.3g} km".format(length/1000.0) # int(_meta['PIPELINE_LENGTH_M'])

    if 'FLUID' in _meta:
        new_meta["fluid"] = _meta['FLUID']
    elif 'FLUID_CONVEYED' in _meta:
        new_meta["fluid"] = _meta['FLUID_CONVEYED']    

    if 'DIAMETER' in _meta:
        #new_meta["Dnom"] = _meta['DIAMETER']
        #new_meta["Do"] = _meta['DIAMETER']
        if ('UNITS' in _meta and _meta['UNITS'].lower()=='inch' or
           'DIAMETER_UNITS' in _meta and _meta['DIAMETER_UNITS'].lower()=='inch'):
            new_meta["Do"] = '{:.3g} in'.format(_meta['DIAMETER']) # _meta['DIAMETER']*25.4
        #new_meta["Do"] = int(new_meta["Do"]) # round(new_meta["Do"], 3)
        else:
            new_meta["Do"] = "{:.1g} mm".format(round(_meta['DIAMETER']))

    if 'STATUS' in _meta:
        new_meta["status"] = _meta['STATUS']

    #if 'COMMENTS' in _meta:
    #    new_meta["comments"] = _meta['COMMENTS']        

    #if 'INST_TYPE' in _meta:
    #    new_meta["INST_TYPE"] = _meta['INST_TYPE']         

    if 'INSULATION_COATING_TYPE' in _meta:
        new_meta["INSULATION_COATING_TYPE"] = _meta['INSULATION_COATING_TYPE']           

    if 'INTERNAL_DIAMETER_MM' in _meta:
        new_meta["Di"] = '{:.1g} mm'.format(_meta['INTERNAL_DIAMETER_MM']) # int(_meta['INTERNAL_DIAMETER_MM'])        

    if 'WALL_THICKNESS_MM' in _meta:
        new_meta["WT"] = round(_meta['WALL_THICKNESS_MM'])           
        
    if 'OPERATING_PRESSURE_MAX_BARG' in _meta:
        new_meta["MOP"] = "{:.1g} bar".format(_meta['OPERATING_PRESSURE_MAX_BARG']) # int(_meta['OPERATING_PRESSURE_MAX_BARG'])        
        
    _f['properties'] = new_meta.copy()
        #_f['properties'] = {k:v for k,v in _meta.items() if v is not None}


# add some top-level metadata into the "crs" object
crs = OGA_pl_data.setdefault("crs", {})
props = crs.setdefault("properties", {})
props["ts"] = datetime.utcnow().isoformat()
props["url"] = "qwilka.com"
props["src_url"] = "https://github.com/qwilka/EngNotes/blob/master/OGA_data/OGA_pipelines_shp2geojson.py"
"""
props["src_data"] = [
{
"filename": OGA_zip_fname,
"url": "https://data-ogauthority.opendata.arcgis.com/datasets/oga-offshore-zipped-shapefiles-wgs84",
"ts": "2020-07-23"
},
{
"filename": NDR_pipelines_fname,
"url": "https://ndr.ogauthority.co.uk",
"ts": "2020-07-27"
}
]
"""


with open(geojson_fname, 'w') as fh:
    json.dump(OGA_pl_data, fh)

# https://github.com/TNOCS/minify-geojson
# this seems to strip out the "crs" object...
if minify_geojson:
    commandList = [
        'minify-geojson',
        "--verbose",
        "--coordinates", "5",
        geojson_fname
    ]
    try:
        op = subprocess.run(commandList, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        print(f"WARNING: cannot minify geojson file {geojson_fname}: {err} {op.stderr.decode('UTF-8')}.")
    else:
        print(f"INFO: minify-geojson: {op.stdout.decode('UTF-8')}")
        if op.stderr:
            print(f"WARNING: minify-geojson: {op.stderr.decode('UTF-8')}")

