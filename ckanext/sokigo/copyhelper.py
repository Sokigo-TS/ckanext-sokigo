import ckan.lib.helpers as h
import ckan.plugins as p
import ckan.model as m
import ckan.plugins.toolkit as t
import ckan.logic as l

import ckan.lib.navl.dictization_functions as dict_fns
from ckan.common import c
from ckan.views.home import CACHE_PARAMETERS
from ckan.lib.plugins import lookup_package_plugin

from ckan.lib.search import SearchIndexError
from six import string_types, text_type

import flask

from flask import Blueprint, jsonify, request, send_file, abort
import tempfile

import logging
import json
import requests
import base64

import ckan.model as model

import json
import os
import ckan.lib.base as base

from ckan.views.admin import admin as admin_blueprint

from flask import Blueprint, render_template, request, redirect, url_for
from ckan.plugins import SingletonPlugin, implements
from ckan.plugins.toolkit import config

from ckan.common import config as ckan_config
import ckan.lib.jobs as jobs

from ckan.logic import ValidationError
from ckanext.scheming.helpers import scheming_get_dataset_schema
from ckan.lib.helpers import lang

tuplize_dict = l.tuplize_dict
clean_dict = l.clean_dict
parse_params = l.parse_params
flatten_to_string_key = l.flatten_to_string_key

logger = logging.getLogger(__name__)

copy_blueprint = Blueprint('copy', __name__, url_prefix='/dataset/copy')

sysadmin_blueprint = Blueprint('ckan_admin', __name__, url_prefix='/ckan-admin')

nonadmin_blueprint = Blueprint('ckan_nonadmin', __name__, url_prefix='/')

dataset_resources_blueprint = Blueprint(
    'dataset_resources',
    __name__,
    url_prefix='/dataset'
)

from urllib.parse import quote

from ckan.lib.search import rebuild

from ckan.common import _,  current_user
from collections import OrderedDict

from ckanext.scheming.helpers import (
    scheming_dataset_schemas, scheming_get_dataset_schema,
   scheming_field_by_name , scheming_get_child_fields
    )

all_helpers = {}

def helper(fn):
    """
    collect helper functions into ckanext.editor.all_helpers dict
    """
    all_helpers[fn.__name__] = fn
    return fn

@sysadmin_blueprint.before_request
def before_request() -> None:
    try:
        context: Context = {
            "user": current_user.name,
            "auth_user_obj": current_user
        }
        l.check_access(u'sysadmin', context)
    except l.NotAuthorized:
        base.abort(403, _(u'Need to be system administrator to administer'))


@copy_blueprint.route('/<id>/resources', methods=['GET','POST'])
def copy_resources(id, data=None, errors=None, error_summary=None):
    context = {
        'model': m,
        'session': m.Session,
        'user': p.toolkit.c.user or p.toolkit.c.author,
        'auth_user_obj': p.toolkit.c.userobj,
        'save': 'save' in t.request.form,
    }
        
    # check permissions
    try:
        t.check_access('package_create', context)
    except t.NotAuthorized:
        t.abort(401, t._('Unauthorized to copy this package'))

    # get package type
    if data and 'type' in data:
        package_type = data['type']
    else:
        package_type = _guess_package_type(True)

    resources = None
    if data is None:
        data = t.get_action('package_show')(None, {'id': id})
        # generate new unused package name
        data['title'] = u'{} {}'.format(t._('Copy of'), data['title'])
        data['name'] = '{}{}'.format(data['name'],t._('-copy'))
        while True:
            try:
                _ = t.get_action('package_show')(None, {'name_or_id': data['name']})
            except l.NotFound:
                break
            else:
                import random
                data['name'] = '{}{}-{}'.format(data['name'], t._('-copy'), random.randint(1, 100))

        # remove unnecessary attributes from the dataset
        remove_attrs = ['id', 'revision_id', 'metadata_created', 'metadata_modified', 'revision_timestamp']
        for attr in remove_attrs:
            if attr in data:
                del data[attr]

        # process package resources
        resources = data.pop('resources', [])
        remove_attrs = ('id', 'revision_id', 'created', 'last_modified', 'package_id')
        for resource in resources:
            for attr in remove_attrs:
                if attr in resource:
                    del resource[attr]

        c.resources_json = h.json.dumps(resources)

        # convert tags if not supplied in data
        if data and not data.get('tag_string'):
            data['tag_string'] = ', '.join(
                h.dict_list_reduce(data.get('tags', {}), 'name'))

        # if we are creating from a group then this allows the group to be
        # set automatically
        data['group_id'] = t.request.args.get('group') or \
                            t.request.args.get('groups__0__id')

    form_snippet = 'package/copy_package_form.html'
    c.form_action = t.url_for('copy.copy_resources', id=id)

    if context['save'] and t.request.method == 'POST':
        data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
            t.request.form, ignore_keys=CACHE_PARAMETERS))))

        data['resources'] = resources

        try:
            pkg_dict = t.get_action('package_create')(context, data)
        except l.NotAuthorized:
            t.abort(403, _('Unauthorized to read package %s') % '')
        except l.NotFound as e:
            t.abort(404, _('Dataset not found'))
        except dict_fns.DataError:
            t.abort(400, _(u'Integrity Error'))
        except SearchIndexError as e:
            try:
                exc_str = text_type(repr(e.args))
            except Exception:  # We don't like bare excepts
                exc_str = text_type(str(e))
            t.abort(500, _(u'Unable to add package to search index.') + exc_str)
        except t.ValidationError as e:
            data['state'] = 'none'
            c.data = data
            c.errors_json = h.json.dumps(e.error_dict)
            form_vars = {'data': data, 'errors': e.error_dict,
                            'error_summary': e.error_summary,
                            'action': 'new', 'stage': data['state'],
                            'dataset_type': package_type}

            extra_vars = {'form_vars': form_vars,
                            'form_snippet': form_snippet,
                            'dataset_type': package_type,
                            'pkg': data['name'],
                            'pkg_dict': data}

            return t.render('package/copy.html', extra_vars=extra_vars)

        else:
            return h.redirect_to(controller='dataset', action='read', id=pkg_dict['name'])

    logger.info("Dictionary: %s", json.dumps(data, indent=2))
 
    c.data = data
    c.errors_json = h.json.dumps(errors)
    
    form_vars = {'data': data, 'errors': errors or {},
                     'error_summary': error_summary or {},
                     'action': 'new', 'stage': data['state'],
                     'dataset_type': package_type}                

    extra_vars = {'form_vars': form_vars,
                    'form_snippet': form_snippet,
                    'dataset_type': package_type,
                    'pkg': data['name'],
                    'pkg_dict': data}

    return t.render('package/copy.html', extra_vars=extra_vars)


@copy_blueprint.route('/<id>', methods=['GET'])
def copy(id):
    context = {
        'model': m,
        'session': m.Session,
        'user': p.toolkit.c.user or p.toolkit.c.author,
        'auth_user_obj': p.toolkit.c.userobj,
        'save': 'save' in t.request.form,
    }

    # check permissions
    try:
        t.check_access('package_create', context)
    except t.NotAuthorized:
        t.abort(401, t._('Unauthorized to copy this package'))

    data_dict = {'id': id}
    data = t.get_action('package_show')(None, data_dict)

    # change dataset title and name
    data['name'] = '{}{}'.format(data['name'], t._('-copy'))
    while True:
        try:
            _pkg = t.get_action('package_show')(None, {'name_or_id': data['name']})
        except l.NotFound:
            break
        else:
            import random
            data['name'] = '{}{}-{}'.format(data['name'], t._('-copy'), random.randint(1, 100))

    data['title'] = u'{} {}'.format(t._('Copy of'), data['title'])

    # remove unnecessary attributes from the dataset
    remove_attrs = ['id', 'revision_id', 'metadata_created', 'metadata_modified',
                    'resources', 'revision_timestamp']
    for attr in remove_attrs:
        if attr in data:
            del data[attr]

    if data and 'type' in data:
        package_type = data['type']
    else:
        package_type = _guess_package_type(True)

    data = data or clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
        t.request.args, ignore_keys=CACHE_PARAMETERS))))
    c.resources_json = h.json.dumps(data.get('resources', []))

    # convert tags if not supplied in data
    if data and not data.get('tag_string'):
        data['tag_string'] = ', '.join(
            h.dict_list_reduce(data.get('tags', {}), 'name'))

    # if we are creating from a group then this allows the group to be
    # set automatically
    data['group_id'] = t.request.args.get('group') or \
                        t.request.args.get('groups__0__id')

    # in the phased add dataset we need to know that
    # we have already completed stage 1
    stage = ['active']
    if data.get('state', '').startswith('draft'):
        stage = ['active', 'complete']

    form_snippet = lookup_package_plugin(package_type=package_type).package_form()
    form_vars = {'data': data, 'errors': {},
                    'error_summary': {},
                    'action': 'new', 'stage': stage,
                    'dataset_type': package_type, }

    c.errors_json = h.json.dumps({})

    # override form action to use built-in package controller
    c.form_action = t.url_for('dataset.new')

    lookup_package_plugin(package_type=package_type).setup_template_variables(context, {})
    new_template = lookup_package_plugin(package_type=package_type).new_template()
    extra_vars = {'form_vars': form_vars,
                    'form_snippet': form_snippet,
                    'dataset_type': package_type,
                    'pkg': data['name'],
                    'pkg_dict': data}

    return t.render(new_template, extra_vars=extra_vars)

@sysadmin_blueprint.route('/actors', methods=['GET', 'POST'])  # Allow both GET and POST
def Editor():
    JSON_FILES_DIRECTORY = r'c:\app\src\ckan\publisher_data'
    
    FILE_NAME_MAPPING = ckan_config.get('file_name_mapping')
    
    if FILE_NAME_MAPPING:
        FILE_NAME_MAPPING= json.loads(FILE_NAME_MAPPING)
    else:
        FILE_NAME_MAPPING = {
        "publisherdata.json": "Utgivare",
        "producerdata.json": "Informationsägare",
        "maintainerdata.json": "Informationsförvaltare"
        }
            
    
    FIELD_NAME_MAPPING = ckan_config.get('field_name_mapping')
    if FIELD_NAME_MAPPING:
        FIELD_NAME_MAPPING = json.loads(FIELD_NAME_MAPPING)
    else:
        FIELD_NAME_MAPPING = { "publisherdata.json": "publisher_name", "producerdata.json": "creator_name", "maintainerdata.json": "contact_name" }    

    # Type options stored as a mapping of Name -> URI
    TYPE_OPTIONS = OrderedDict([
        ( "Lokal myndighet/kommun", "http://purl.org/adms/publishertype/LocalAuthority"),
        ("Akademia/Vetenskaplig organisation", "http://purl.org/adms/publishertype/Academia-ScientificOrganisation"),
        ("Företag", "http://purl.org/adms/publishertype/Company"),
        ("Industrikonsortium", "http://purl.org/adms/publishertype/IndustryConsortium"),       
        ( "Nationell myndighet", "http://purl.org/adms/publishertype/NationalAuthority"),
        ("Icke-statlig organisation", "http://purl.org/adms/publishertype/NonGovernmentalOrganisation"),
        ("Ej vinstdrivande organisation", "http://purl.org/adms/publishertype/NonProfitOrganisation"),
        ("Privatperson(er)", "http://purl.org/adms/publishertype/PrivateIndividual(s)"),        
        ("Regional myndighet/landsting", "http://purl.org/adms/publishertype/RegionalAuthority"),
        ("Standardiseringsorganisation", "http://purl.org/adms/publishertype/NonProfitOrganisation"),
        ("Över-/mellanstatlig myndighet", "http://purl.org/adms/publishertype/SupraNationalAuthority")
    ])    
                
    # Ensure the directory for JSON files exists
    if not os.path.exists(JSON_FILES_DIRECTORY):
        os.makedirs(JSON_FILES_DIRECTORY)

    # Get available JSON files & make them readable
    json_files = [
        {"file_name": f, "display_name": FILE_NAME_MAPPING.get(f, f)}  # Use mapping or raw filename if not found
        for f in os.listdir(JSON_FILES_DIRECTORY) if f.endswith('.json')
    ]

    # Determine selected file
    selected_file = request.args.get('file') if request.args.get('file') else None
    json_data = None
    error = None

    # Load JSON file if selected
    if selected_file:
        selected_file_path = os.path.join(JSON_FILES_DIRECTORY, selected_file)
        try:
            with open(selected_file_path, 'r') as f:
                json_data = json.load(f)
        except json.JSONDecodeError:
            error = f"Could not parse {selected_file} as valid JSON."
        except Exception as e:
            error = str(e)

    ### **Handling the POST request for saving data**
    if request.method == 'POST':
        if selected_file:
            selected_file_path = os.path.join(JSON_FILES_DIRECTORY, selected_file)
            objects_count = int(request.form.get('objects_count', 0))
            rows = []

            # Construct JSON object from form fields
            for i in range(objects_count):
                row = {
                    'id': request.form.get(f'id_{i}', ''),
                    'name': request.form.get(f'name_{i}', ''),
                    'uri': request.form.get(f'uri_{i}', ''),
                    'email': request.form.get(f'email_{i}', ''),
                    'type': request.form.get(f'type_{i}', ''),
                    'url': request.form.get(f'url_{i}', ''),
                }
                rows.append(row)

            # Save updated JSON back to file
            try:
                with open(selected_file_path, 'w') as f:
                    json.dump(rows, f, indent=4)
                
                fieldName = FIELD_NAME_MAPPING.get(selected_file, None)
                
                if fieldName and selected_file_path:
                    t.enqueue_job(
                                    add_background_job_for_update_datasets,
                                    [selected_file_path, fieldName],
                                )
                
                # Redirect to prevent form resubmission issues
                return redirect(url_for('.Editor', file=selected_file))
            except Exception as e:
                error = str(e)

    return render_template(
        'admin/JsonEditor.html',
        json_files=json_files,
        selected_file=selected_file,
        json_data=json_data or [],
        error=error,
        type_options=TYPE_OPTIONS 
    )   


def _guess_package_type(expecting_name=False):
    """
        Guess the type of package from the URL handling the case
        where there is a prefix on the URL (such as /data/package)
    """

    # Special case: if the rot URL '/' has been redirected to the package
    # controller (e.g. by an IRoutes extension) then there's nothing to do
    # here.
    if flask.request.path == '/':
        return 'dataset'

    parts = [x for x in flask.request.path.split('/') if x]

    idx = -1
    if expecting_name:
        idx = -2

    pt = parts[idx]
    if pt == 'package':
        pt = 'dataset'

    return pt
    
@helper
def get_landingpage_news():
    try:
        api_url =  ckan_config.get('landingpage_url')
        username = ckan_config.get('landingpage_username') 
        password = ckan_config.get('landingpage_password') 
                
        # Create base64-encoded credentials
        credentials = f"{username}:{password}"
        base64_credentials = base64.b64encode(credentials.encode()).decode()
        
        # Define the headers with basic authentication
        headers = {"Authorization": f"Basic {base64_credentials}"}
        
        # Perform the HTTP GET request with basic authentication
        response = requests.get(api_url, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            
            # Parse the JSON response
            response_data = json.loads(response.text)
            
            # Extract the value from the storage object
            html_content = response_data['body']['storage']['value']
        
            return html_content
        else:
            print(f"Failed to fetch API response. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None          

@helper
def get_datasets(selected):
    datasets = model.Session.query(model.Package)

    if selected:
        selected_id = selected.get('id', None)
        if selected_id:
            # Remove the selected dataset ID from the list of datasets
            datasets = datasets.filter(model.Package.id != selected_id)
    
      
    base_url = ckan_config.get('ckan.site_url')  # Get the site URL from configuration
    dataset_choices = [{
        'value': r.id,
        'label': f'<a href="{base_url}/dataset/{quote(r.id)}" target="_blank">{r.name}</a>'
    } for r in datasets if r.state == 'active']

    return dataset_choices

@helper
def get_dataset_title(dataset_id):
    
    try:
        dataset = t.get_action('package_show')( {
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                }, {'id': dataset_id})
        return dataset['title']
    except t.ObjectNotFound:
        return None

@helper
def get_publisher_from_json(selected):
    json_file_path = r'c:\app\src\ckan\publisher_data\publisherdata.json'
    return get_drop_down_data_from_file(json_file_path, selected)
    
@helper
def get_producer_from_json(selected):
    json_file_path = r'c:\app\src\ckan\publisher_data\producerdata.json'
    return get_drop_down_data_from_file(json_file_path, selected)

@helper
def get_maintainer_from_json(selected):
    json_file_path = r'c:\app\src\ckan\publisher_data\maintainerdata.json'
    return get_drop_down_data_from_file(json_file_path, selected)    

def get_drop_down_data_from_file(json_file_path, selected):

    if not os.path.exists(json_file_path):
        return []

    try:

        # Read and parse the JSON file
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        
        # Check if data is empty
        if not data:
            return []   
            
        # Extract selected_id if provided
        selected_id = selected.get('id') if selected else None    
    
        # Process the data to the desired format
        dataset_choices = [{
            'value': item['id'],
            'label': item['name'],
            'uri': item['uri'],
            'email': item['email'],
            'type': item['type'],
            'url': item['url']
        } for item in data if item['id'] != selected_id]
    
        return dataset_choices
    except (json.JSONDecodeError, IOError):
        # Handle cases where the file can't be read or is not a valid JSON
        return []



def add_org_extras(package_id, organization_id):
    try:
        logger.info("add org extras called")
        logger.info(package_id)   
               
        organization : dict[str, Any] = t.get_action("organization_show")({
                "ignore_auth": True,
                "use_cache": False,
                "validate": False,
            },{
                "id": organization_id,
            },)        
        
        new_extras_added = False
        field_names_to_inherit = ckan_config.get('fields_inherit_from_organization')
            
        if field_names_to_inherit:
            rebuild(package_id)
    
            params = {
                    "id": package_id,
                    }
                
            datasetPackage: dict[str, Any] = t.get_action("package_show")({
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                },params,)
            
            field_names_to_inherit = [field.strip() for field in field_names_to_inherit.split(',')]
            logger.info(f'field name - {field_names_to_inherit}')
            for field_to_add in field_names_to_inherit:
                if field_to_add in organization:
                    value = get_field_value(datasetPackage, field_to_add)
                    logger.info(f'field name - {field_to_add} and value - {value}')
                    if not value or value == "[]" or value == "": 
                        
                        datasetPackage[field_to_add] = organization[field_to_add]
                        new_extras_added = True
                    else:
                        datasetPackage[field_to_add] = value                          
            
            
            if 'extras' in organization:        
                for organization_extra in organization["extras"]:
                    organization_extra_key = organization_extra['key']
                    organization_extra_value = organization_extra['value']
                                    
                    # Check if the key already exists in datasetPackage['extras']
                    key_exists = any(extra['key'] == organization_extra_key for extra in datasetPackage.get('extras', []))
                    
                    if not key_exists:
                        logger.info(f"key - {organization_extra_key} not exists in dataset. Adding")
                        new_extras_added = True
                        # If the key doesn't exist, append the key-value pair to datasetPackage['extras']
                        datasetPackage['extras'].append({'key': organization_extra_key, 'value': organization_extra_value})
                        
            
            custom_metadata_fields = ckan_config.get('custom_metadata_fields')
    
            logger.info(f'custom_metadata_fields -{custom_metadata_fields}')
            
            custom_metadata_fields = [field.strip() for field in custom_metadata_fields.split(',')]
            
            if new_extras_added:
                logger.info('updating package')
     
                if 'extras' in datasetPackage:
                    extras_list = datasetPackage['extras']
                    datasetPackage['extras'] = [item for item in extras_list if item.get('key')  not in custom_metadata_fields]
                
                t.get_action('package_update')({
                        "ignore_auth": True,
                        "use_cache": False,
                        "validate": False,
                    }, datasetPackage)
                
                rebuild(package_id)
                                            
    except Exception as e:
        return         
            
            
def get_field_value(package, field):
    val = fetch_value_from_extras(package['extras'], field)
    
    val = val if val else package[field] if field in package else None
    
    return val     
   

def fetch_value_from_extras(extras_list, key):
    for item in extras_list:
        if item.get('key') == key:
            return item.get('value')
    return None            
    
@helper
def get_custom_metadata_fields():

    custom_metadata_fields = ckan_config.get('custom_metadata_fields')

    # Set custom added metadata fields in package so that it can be syndicated.
    if custom_metadata_fields:
        custom_metadata_fields = [field.strip() for field in custom_metadata_fields.split(',')]  
        return custom_metadata_fields
    return None  

@helper
def get_ordered_metadata_fields():

    custom_metadata_fields = ckan_config.get('ordered_metadata_fields')

    # Set custom added metadata fields in package so that it can be syndicated.
    if custom_metadata_fields:
        custom_metadata_fields = [field.strip() for field in custom_metadata_fields.split(',')]  
        return custom_metadata_fields
    return None      

@copy_blueprint.route('UndeleteDataset/<package_id>', methods=['GET', 'POST'])
def UndeleteDataset(package_id):
    params = {
                "id": package_id,
            }
            
    datasetPackage: dict[str, Any] = t.get_action("package_show")({
            "ignore_auth": True,
            "use_cache": False,
            "validate": False,
        },params,)
    
    datasetPackage["state"] = "active"
    
    custom_metadata_fields = ckan_config.get('custom_metadata_fields')
            
    custom_metadata_fields = [field.strip() for field in custom_metadata_fields.split(',')]
    
    if 'extras' in datasetPackage:
        extras_list = datasetPackage['extras']
        datasetPackage['extras'] = [item for item in extras_list if item.get('key')  not in custom_metadata_fields]
    
    t.get_action('package_update')({
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                }, datasetPackage)   
    rebuild(package_id)  
    
    return t.redirect_to(f'/dataset/{datasetPackage["id"]}')


def add_background_job_for_update_datasets(json_path, fieldName):
    
    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    logger.info(f"Fetching datasets")
    
    # Fetch all datasets
    datasets = t.get_action('package_list')( {
            "ignore_auth": True,
            "use_cache": False,
            "validate": False,
        })
    
    logger.info(f"Getting dataset schema")

    schema = scheming_dataset_schemas() 
        
    # Extract dataset
    dataset = schema.get('dataset', {})

    # Extract dataset fields
    dataset_fields = dataset.get('dataset_fields', [])
    
    for dataset in datasets:       
        update_datasets_for_drop_down_fields(dataset, json_data, fieldName, dataset_fields)
        

def update_datasets_for_drop_down_fields(dataset, json_data, field_name, dataset_fields):
    logger.info(f"update_datasets_for_drop_down_fields executed for dataset - {dataset} and field name - {field_name}")
        
    json_lookup = {item['id']: item for item in json_data}    
    
    json_lookup.update({item['name']: item for item in json_data if 'name' in item and item['name']})
    
    field = scheming_field_by_name(dataset_fields, field_name)  
                
    custom_metadata_fields = ckan_config.get('custom_metadata_fields')
    custom_metadata_fields = [field.strip() for field in custom_metadata_fields.split(',')]

    try:
        datasetDetails = t.get_action('package_show')( {
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                }, {'id': dataset})
                
        dropDownValue = get_field_value(datasetDetails ,field_name)
        if dropDownValue and dropDownValue in json_lookup:
            
            # Fetch matching node from JSON
            matching_node = json_lookup[dropDownValue]
            
            logger.info(f"matching_node : {matching_node}")
            
            datasetDetails[field_name] = matching_node.get('id')

            # Iterate over child fields
            for child in scheming_get_child_fields(field):
                logger.info(f"child field - {child}")
                
                json_value = matching_node.get(child.split('_')[-1])  # Get value from JSON
                dataset_value = get_field_value(datasetDetails ,child) 
                
                datasetDetails[child] = json_value                                  
                
            logger.info('updating package')
    
            if 'extras' in datasetDetails:
                extras_list = datasetDetails['extras']
                datasetDetails['extras'] = [item for item in extras_list if item.get('key')  not in custom_metadata_fields]
                            
            t.get_action('package_update')({
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                }, datasetDetails)
    except Exception as e:
        logger.error(f"Error processing dataset {dataset}: {str(e)}")  
      
      
@nonadmin_blueprint.route('/download_package/<package_id>', methods=['GET', 'POST'])  # Allow both GET and POST      
def download_package(package_id):
    """
    Download a dataset package as JSON file using internal CKAN action API.
    """
    try:
        context = {'model': model, 'session': model.Session, 'ignore_auth': True}
        package_show = t.get_action('package_show')
        result = package_show(context, {'id': package_id})

        # Write result to a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', suffix='.json', delete=False) as tmp_file:
            json.dump(result, tmp_file, indent=2, ensure_ascii=False)
            tmp_file_path = tmp_file.name

        # Serve file as download
        return send_file(
            tmp_file_path,
            mimetype='application/json',
            as_attachment=True,
            download_name=f"{result['name']}.json"
        )
    except t.ObjectNotFound:
        return f"Package with ID '{package_id}' not found.", 404
    except Exception as e:
        return f"Error: {str(e)}", 500   
    
    
@dataset_resources_blueprint.route('/<id>/resources')
def resources(id):
    # Reuse CKAN core logic to render the dataset page
    return t.render(
        'package/resources.html',
        extra_vars={
            'pkg_dict': t.get_action('package_show')(
                {}, {'id': id}
            )
        }
    )    

    
@helper
def controlled_list_choices(field):
    field_name = field.get('field_name')
    data = load_controlled_lists()

    raw = data.get(field_name)
    if not isinstance(raw, list):
        return []

    choices = []

    for item in raw:
        if isinstance(item, str):
            value = item.strip()
            if value:
                choices.append({'value': value, 'label': value})

        elif isinstance(item, dict):
            value = item.get('value')
            label = item.get('label', value)
            if value:
                choices.append({'value': value, 'label': label})

    return choices






@sysadmin_blueprint.route('/ControlledLists', methods=['GET', 'POST'])
def ControlledLists():
    field_names = _allowed_field_names()
    fields = _allowed_fields()

    selected = request.args.get('field')

    if selected not in field_names:
        selected = None

    data = load_controlled_lists()

    if request.method == 'POST':
        if selected not in field_names:
            abort(403)  # extra safety

        values = json.loads(request.form['values'])
        data[selected] = values
        _save_controlled_lists(data)

        return redirect(url_for('.ControlledLists', field=selected))

    return t.render(
        'admin/controlled_lists.html',
        extra_vars={
            'fields': fields,
            'selected': selected,
            'values': json.dumps(data.get(selected, []) if selected else [],indent=2)
        }
    )

  
def get_or_create_controlled_lists(allowed_fields):
    ctx = {'ignore_auth': True}

    try:
        data = l.get_action('config_option_show')(
            ctx, {'key': 'controlled_lists'}
        )
    except ValidationError:
        # Runtime creation
        data = {f: [] for f in allowed_fields}
        l.get_action('config_option_update')(
            ctx,
            {'key': 'controlled_lists', 'value': data}
        )

    return data    

def _controlled_lists_path():
    return 'c:/app/src/ckan/drop_down_fields_data/MultiSelect_Lists.json' 

def _allowed_field_names():
    return ckan_config.get('controlled_lists_fields', '').split()


def _allowed_fields():
    allowed = _allowed_field_names()

    # Get default dataset type
    dataset_type = ckan_config.get('ckan.default_dataset_type', 'dataset')

    schema = scheming_get_dataset_schema(dataset_type)

    fields = []

    for f in schema.get('dataset_fields', []):
        name = f.get('field_name')

        if name in allowed:
            label = f.get('label')

            # Handle multilingual label
            if isinstance(label, dict):
                label = label.get(lang(), name)

            fields.append({
                'value': name,
                'label': label or name
            })

    return fields

def load_controlled_lists():
    field_names = _allowed_field_names()
    path = _controlled_lists_path()

    if not os.path.exists(path):
        data = {f: [] for f in field_names}
        _save_controlled_lists(data, path)
        return data

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed = False

    for f in field_names:
        if f not in data:
            data[f] = []
            changed = True

    if changed:
        _save_controlled_lists(data, path)

    return data

def _save_controlled_lists(data, path=None):
    path = path or _controlled_lists_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)