.. You should enable this project on travis-ci.org and coveralls.io to make
   these badges work. The necessary Travis and Coverage config files have been
   generated for you.

.. image:: https://travis-ci.org/sokigo/ckanext-sokigo.svg?branch=master
    :target: https://travis-ci.org/sokigo/ckanext-sokigo

.. image:: https://coveralls.io/repos/sokigo/ckanext-sokigo/badge.svg
  :target: https://coveralls.io/r/sokigo/ckanext-sokigo

.. image:: https://pypip.in/download/ckanext-sokigo/badge.svg
    :target: https://pypi.python.org/pypi//ckanext-sokigo/
    :alt: Downloads

.. image:: https://pypip.in/version/ckanext-sokigo/badge.svg
    :target: https://pypi.python.org/pypi/ckanext-sokigo/
    :alt: Latest Version

.. image:: https://pypip.in/py_versions/ckanext-sokigo/badge.svg
    :target: https://pypi.python.org/pypi/ckanext-sokigo/
    :alt: Supported Python versions

.. image:: https://pypip.in/status/ckanext-sokigo/badge.svg
    :target: https://pypi.python.org/pypi/ckanext-sokigo/
    :alt: Development Status

.. image:: https://pypip.in/license/ckanext-sokigo/badge.svg
    :target: https://pypi.python.org/pypi/ckanext-sokigo/
    :alt: License

=============
ckanext-sokigo
=============

This extension offers the following functionality:

* customized english and swedish translations for the dataset and resource templates

* re-ordered the default design of the dataset and resource templates

* "copy dataset" feature that enables faster creation of new datasets based on existing ones

* customized home page that contains GeoDirekt logo

* enriched dataset and resources with additional metadata fields


------------
Requirements
------------

This extension is developed and compatible with CKAN version 2.8.5


------------
Installation
------------

To install ckanext-sokigo:

1. Activate your CKAN virtual environment, for example::

     . /usr/lib/ckan/default/bin/activate

2. Install the ckanext-sokigo Python package into your virtual environment::

     pip install -e ckanext-sokigo

3. Add ``sokigo`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu::

     sudo service apache2 reload


---------------
Config Settings
---------------

No additional config settings are needed to use the sokigo extension

------------------------
Development Installation
------------------------

To install ckanext-sokigo for development, activate your CKAN virtualenv and
do::

    git clone https://github.com/sokigo/ckanext-sokigo.git
    cd ckanext-sokigo
    python setup.py develop
    pip install -r dev-requirements.txt


-----------------
Running the Tests
-----------------

To run the tests, do::

    nosetests --nologcapture --with-pylons=test.ini

To run the tests and produce a coverage report, first make sure you have
coverage installed in your virtualenv (``pip install coverage``) then run::

    nosetests --nologcapture --with-pylons=test.ini --with-coverage --cover-package=ckanext.sokigo --cover-inclusive --cover-erase --cover-tests


---------------------------------
Translating the extension
---------------------------------

The English and Swedish translations for this extensions are located in: `ckanext/sokigo/i18n/`

In order to further enrich or update existing translations edit the ".po" catalog files. Below you can find a reference to the commands related to the translation:

To initialize new language type::

     python setup.py init_catalog -l <LANG>

To update existing catalog type::

     python setup.py update_catalog

To extract messages type::

     python setup.py extract_messages

To compile the translations type::

       python setup.py compile_catalog



