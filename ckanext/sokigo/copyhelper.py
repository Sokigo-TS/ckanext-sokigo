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

from flask import Blueprint
import logging
import json
import requests
import base64

import ckan.model as model

import json
import os

from ckan.common import config as ckan_config

tuplize_dict = l.tuplize_dict
clean_dict = l.clean_dict
parse_params = l.parse_params
flatten_to_string_key = l.flatten_to_string_key

logger = logging.getLogger(__name__)

copy_blueprint = Blueprint('copy', __name__, url_prefix='/dataset/copy')

from urllib.parse import quote

from ckan.lib.search import rebuild

all_helpers = {}

def helper(fn):
    """
    collect helper functions into ckanext.editor.all_helpers dict
    """
    all_helpers[fn.__name__] = fn
    return fn

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

#class CopyController(PackageController):
#
#    p.implements(p.IBlueprint)
#
#    def get_blueprint(self):
#        blueprint = Blueprint('copy', self.__module__, url_prefix='/dataset/copy')
#        rules = [
#            ('/<id>/resources', 'copy_resources', copy_resources),
#            ('/<id>', 'copy', copy),
#        ]
#        for rule in rules:
#            blueprint.add_url_rule(*rule)
#
#        return blueprint


def add_org_extras(package_id:str):
   
    logger.info(package_id)

    rebuild(package_id)

    params = {
                "id": package_id,
            }
            
    datasetPackage: dict[str, Any] = t.get_action("package_show")({
            "ignore_auth": True,
            "use_cache": False,
            "validate": False,
        },params,)
        
    organization_id = datasetPackage["organization"]["id"]
    
    if not organization_id:
        return 
        
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
                    new_extras_added = True
                    # If the key doesn't exist, append the key-value pair to datasetPackage['extras']
                    datasetPackage['extras'].append({'key': organization_extra_key, 'value': organization_extra_value})
                    
        
        custom_metadata_fields = ckan_config.get('custom_metadata_fields')

        logger.info(f'custom_metadata_fields -{custom_metadata_fields}')
        
        custom_metadata_fields = [field.strip() for field in custom_metadata_fields.split(',')]
        
        logger.info('updating package from org')
        if new_extras_added:
            if 'extras' in datasetPackage:
                extras_list = datasetPackage['extras']
                datasetPackage['extras'] = [item for item in extras_list if item.get('key')  not in custom_metadata_fields]
            
            t.get_action('package_update')({
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                }, datasetPackage)   
            rebuild(package_id)  
            
            
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
    
    t.get_action('package_update')({
                    "ignore_auth": True,
                    "use_cache": False,
                    "validate": False,
                }, datasetPackage)   
    rebuild(package_id)  
    
    return t.redirect_to(f'/dataset/{datasetPackage["id"]}')

     
