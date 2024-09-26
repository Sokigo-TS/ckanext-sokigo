import os
import logging
import ckan.plugins as p
import ckan.plugins.toolkit as t
import ckanext.sokigo.copyhelper as copyhelper
from ckan.lib.plugins import DefaultTranslation
from flask import Blueprint
from typing import Any, cast
from ckan.types import Context, Schema, Validator, ValidatorFactory

from ckanext.sokigo.copyhelper import copy_blueprint

from ckanext.sokigo import copyhelper
import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

log = logging.getLogger('ckanext.sokigo')

# SAML2 mapping by name: AD-group name must match organization name.
def saml2_mapping_by_name(saml_info):
    result = {}
    result_log = ''

    if (saml_info is None):
        return result

    capacity = os.environ.get('CKANEXT_SOKIGO_ORGANIZATION_MAPPING_CAPACITY')
    if (capacity is None):
        capacity = 'member'
    if (capacity == ''):
        capacity = 'member'
    
    log.info('Mapping SAML2 groups with organizations by name. Group name must match organization name.')

    if ('groups' in saml_info):
        groups = saml_info['groups']
        for group in groups:
            orgid = group.lower().replace(' ','_').replace('å','a').replace('ä','a').replace('ö','o')
            result_log = result_log + group + '=>' + orgid + ' (' + capacity + '),'
            result.update(
            {
                orgid: {
                    'capacity': capacity,
                    'data': {
                        'id': orgid,
                        'description': group
                    }
                }
            })
    log.info('Mapping result: %s', result_log)
    return result

# SAML2 mapping by list: Use mapping list [ad_group_name]~[ckan_org]~[capacity]
def saml2_mapping_by_list(saml_info):
    result = {}
    result_log = ''
    groups_log = ''

    if (saml_info is None):
        return result

    mapping_list = os.environ.get('CKANEXT_SOKIGO_ORGANIZATION_MAPPING')
    if (mapping_list is None):
        return result

    log.info('Mapping SAML2 groups with organizations by manual list: %s', mapping_list)
        
    if ('groups' in saml_info):
        groups = saml_info['groups']
        # Loop through all groups
        for group in groups:
            groups_log = groups_log + group + ','
            # Loop through all mapping entries
            for mapping in mapping_list.split(';'):
                bits = mapping.split('~')
                # First item is saml2-group and second is ckan-organization. Third item is capacity (member or editor).
                # Check if we're having a match (case-insensitive).
                # Also check that org is not already present in result list.
                if (bits[0].lower() == group.lower() and not(bits[1].lower() in result)):
                    result_log = result_log + group + '=>' + bits[1].lower() + ' (' + bits[2] + '),'
                    result.update(
                    {
                        bits[1].lower(): {
                            'capacity': bits[2],
                            'data': {
                                'id': bits[1].lower(),
                                'description': bits[1]
                            }
                        }
                    })
    log.info('Groups detected: %s', groups_log)
    log.info('Mapping result: %s', result_log)
    return result


class SokigoPlugin(p.SingletonPlugin, t.DefaultDatasetForm, DefaultTranslation):
    p.implements(p.IConfigurer)
    p.implements(p.ITranslation)
    p.implements(p.ITemplateHelpers)
    p.implements(p.IDatasetForm, inherit=True)
    p.implements(p.IBlueprint)
    p.implements(p.IDomainObjectModification, inherit=True)
    p.implements(p.IPackageController, inherit=True)


    def notify(self, entity, operation=None):
        if not operation:
            # This happens on IResourceURLChange
            return

        if not isinstance(entity, model.Package):
            return
        
        params = {
        "id": entity.id,
        }
        
        package: dict[str, Any] = t.get_action("package_show")(
            {
                "ignore_auth": True,
                "use_cache": False,
                "validate": False,
            },
            params,
        )
        
        if "state" in package and package["state"] == "draft":
            t.enqueue_job(
                              copyhelper.add_org_extras,
                              [entity.id],
                          )

      
    # IConfigurer
    def update_config(self, config_):
        t.add_template_directory(config_, 'templates')
        t.add_public_directory(config_, 'public')
        t.add_resource('fanstatic', 'sokigo')

    def get_helpers(self):
        return dict(copyhelper.all_helpers)

    # IBlueprint

    def get_blueprint(self):

        return copy_blueprint
        # rules = [
            # ('/<id>/resources', 'copy_resources', copyhelper.copy_resources),
            # ('/<id>', 'copy', copyhelper.copy),
        # ]
        # for rule in rules:
            # blueprint.add_url_rule(*rule)

        # return blueprint

        # blueprint = Blueprint('copy', self.__module__, url_prefix='/dataset/copy')
        # rules = [
            # ('/<id>/resources', 'copy_resources', copyhelper.copy_resources),
            # ('/<id>', 'copy', copyhelper.copy),
        # ]
        # for rule in rules:
            # blueprint.add_url_rule(*rule)

        # return blueprint

    # IDatasetForm

    def _modify_package_schema(self, schema: Schema):
        defaults = [t.get_validator('ignore_missing')]
        package_defaults = [t.get_validator('ignore_missing'),
                            t.get_converter('convert_to_extras')]

        mandatory_defaults = [t.get_validator('not_empty'),
                            t.get_converter('convert_to_extras')]

        schema.update({
            'metadata_language': package_defaults,
        })

        cast(Schema, schema['resources']).update({
            'resource_language': defaults,
            'completeness': defaults,
            'classification': defaults,
            'update_frequency': defaults,
            'area': defaults,
            'coordinate_system': defaults,
            'scale_factor': defaults,
            'z_min': defaults,
            'z_max': defaults,
            'north': defaults,
            'south': defaults,
            'east': defaults,
            'west': defaults,
        })

        return schema

    def create_package_schema(self):
        schema: Schema = super(SokigoPlugin, self).create_package_schema()
        return self._modify_package_schema(schema)

    def update_package_schema(self):
        schema: Schema = super(SokigoPlugin, self).update_package_schema()
        return self._modify_package_schema(schema)

    def show_package_schema(self) -> Schema:
        schema: Schema = super(SokigoPlugin, self).show_package_schema()
        defaults = [t.get_validator('ignore_missing')]
        package_defaults = [t.get_converter('convert_from_extras'),
                            t.get_validator('ignore_missing')]
        mandatory_defaults = [t.get_validator('not_empty'),
                            t.get_converter('convert_from_extras')]

        schema.update({
            'metadata_language': package_defaults,

        })

        cast(Schema, schema['resources']).update({
            'resource_language': defaults,
            'completeness': defaults,
            'classification': defaults,
            'update_frequency': defaults,
            'area': defaults,
            'coordinate_system': defaults,
            'scale_factor': defaults,
            'z_min': defaults,
            'z_max': defaults,
            'north': defaults,
            'south': defaults,
            'east': defaults,
            'west': defaults,
        })
        return schema

    def is_fallback(self):
        # Return True to register this plugin as the default handler for
        # package types not handled by any other IDatasetForm plugin.
        return True

    def package_types(self):
        # This plugin doesn't handle any special package types, it just
        # registers itself as the default (above).
        return []
 
    