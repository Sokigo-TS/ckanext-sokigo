import ckan.lib.helpers as h
import ckan.plugins as p
import ckan.model as m
import ckan.plugins.toolkit as t
import ckan.logic as l

import ckan.lib.navl.dictization_functions as dict_fns
from ckan.common import c
from ckan.controllers.package import PackageController
from ckan.controllers.home import CACHE_PARAMETERS

from ckan.lib.search import SearchIndexError
from six import string_types, text_type

tuplize_dict = l.tuplize_dict
clean_dict = l.clean_dict
parse_params = l.parse_params
flatten_to_string_key = l.flatten_to_string_key


class CopyController(PackageController):

    def copy_resources(self, id, data=None, errors=None, error_summary=None):
        context = {
            'model': m,
            'session': m.Session,
            'user': p.toolkit.c.user or p.toolkit.c.author,
            'auth_user_obj': p.toolkit.c.userobj,
            'save': 'save' in t.request.params,
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
            package_type = self._guess_package_type(True)

        resources = None
        if data is None:
            data = t.get_action('package_show')(None, {'id': id})
            # generate new unused package name
            data['title'] = 'Copy of {0}'.format(data['title'])
            data['name'] = '{}-copy'.format(data['name'])
            while True:
                try:
                    _ = t.get_action('package_show')(None, {'name_or_id': data['name']})
                except l.NotFound:
                    break
                else:
                    import random
                    data['name'] = '{}-copy-{}'.format(data['name'], random.randint(1, 100))

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

        form_snippet = 'package/copy_package_form.html'
        c.form_action = t.url_for(controller='ckanext.sokigo.controller:CopyController', action='copy_resources', id=id)

        if context['save'] and t.request.method == 'POST':
            data = clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
                t.request.POST, ignore_keys=CACHE_PARAMETERS))))

            data['resources'] = resources

            # convert tags if not supplied in data
            if data and not data.get('tag_string'):
                data['tag_string'] = ', '.join(
                    h.dict_list_reduce(data.get('tags', {}), 'name'))

            # if we are creating from a group then this allows the group to be
            # set automatically
            data['group_id'] = t.request.params.get('group') or \
                               t.request.params.get('groups__0__id')

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
                              'dataset_type': package_type}

                return t.render('package/copy.html', extra_vars=extra_vars)

            else:
                h.redirect_to(controller='package', action='read', id=pkg_dict['name'])

        c.data = data
        c.errors_json = h.json.dumps(errors)
        form_vars = {'data': data, 'errors': errors or {},
                     'error_summary': error_summary or {},
                     'action': 'new', 'stage': data['state'],
                     'dataset_type': package_type}

        extra_vars = {'form_vars': form_vars,
                      'form_snippet': form_snippet,
                      'dataset_type': package_type}

        return t.render('package/copy.html', extra_vars=extra_vars)

    def copy(self, id):
        context = {
            'model': m,
            'session': m.Session,
            'user': p.toolkit.c.user or p.toolkit.c.author,
            'auth_user_obj': p.toolkit.c.userobj,
            'save': 'save' in t.request.params,
        }

        # check permissions
        try:
            t.check_access('package_create', context)
        except t.NotAuthorized:
            t.abort(401, t._('Unauthorized to copy this package'))

        data_dict = {'id': id}
        data = t.get_action('package_show')(None, data_dict)

        # change dataset title and name
        data['name'] = '{}-copy'.format(data['name'])
        while True:
            try:
                _pkg = t.get_action('package_show')(None, {'name_or_id': data['name']})
            except l.NotFound:
                break
            else:
                import random
                data['name'] = '{}-copy-{}'.format(data['name'], random.randint(1, 100))

        data['title'] = 'Copy of {0}'.format(data['title'])

        # remove unnecessary attributes from the dataset
        remove_attrs = ['id', 'revision_id', 'metadata_created', 'metadata_modified',
                       'resources', 'revision_timestamp']
        for attr in remove_attrs:
            if attr in data:
                del data[attr]

        if data and 'type' in data:
            package_type = data['type']
        else:
            package_type = self._guess_package_type(True)

        data = data or clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
            t.request.params, ignore_keys=CACHE_PARAMETERS))))
        c.resources_json = h.json.dumps(data.get('resources', []))

        # convert tags if not supplied in data
        if data and not data.get('tag_string'):
            data['tag_string'] = ', '.join(
                h.dict_list_reduce(data.get('tags', {}), 'name'))

        # if we are creating from a group then this allows the group to be
        # set automatically
        data['group_id'] = t.request.params.get('group') or \
                           t.request.params.get('groups__0__id')

        # in the phased add dataset we need to know that
        # we have already completed stage 1
        stage = ['active']
        if data.get('state', '').startswith('draft'):
            stage = ['active', 'complete']

        form_snippet = self._package_form(package_type=package_type)
        form_vars = {'data': data, 'errors': {},
                     'error_summary': {},
                     'action': 'new', 'stage': stage,
                     'dataset_type': package_type, }

        c.errors_json = h.json.dumps({})

        # override form action to use built-in package controller
        c.form_action = t.url_for(controller='package', action='new')

        self._setup_template_variables(context, {}, package_type=package_type)
        new_template = self._new_template(package_type)
        extra_vars = {'form_vars': form_vars,
                      'form_snippet': form_snippet,
                      'dataset_type': package_type}

        return t.render(new_template, extra_vars=extra_vars)
