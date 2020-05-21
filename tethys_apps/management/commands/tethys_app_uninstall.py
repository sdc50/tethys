"""
********************************************************************************
* Name: tethys_app_uninstall.py
* Author: Nathan Swain
* Created On: August 6, 2015
* Copyright: (c) Brigham Young University 2015
* License: BSD 2-Clause
********************************************************************************
"""
import os
import site
import subprocess
import warnings

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission, Group
from tethys_apps.helpers import get_installed_tethys_apps, get_installed_tethys_extensions


class Command(BaseCommand):
    """
    Command class that handles the uninstall command for uninstall Tethys apps.
    """

    def add_arguments(self, parser):
        parser.add_argument('app_or_extension', nargs='+', type=str)
        parser.add_argument('-e', '--extension', dest='is_extension', default=False, action='store_true')
        parser.add_argument('-f', '--force', dest='is_forced',
                            default=False, action='store_true')

    def handle(self, *args, **options):
        """
        Remove the app from disk and in the database
        """
        from tethys_apps.models import TethysApp, TethysExtension
        app_or_extension = "App" if not options['is_extension'] else 'Extension'
        PREFIX = 'tethysapp' if not options['is_extension'] else 'tethysext'
        item_name = options['app_or_extension'][0]

        # Check for app files installed
        installed_items = get_installed_tethys_extensions() if options['is_extension'] else get_installed_tethys_apps()

        if PREFIX in item_name:
            prefix_length = len(PREFIX) + 1
            item_name = item_name[prefix_length:]

        module_found = True
        if item_name not in installed_items:
            module_found = False

        # Check for app/extension in database
        TethysModel = TethysApp if not options['is_extension'] else TethysExtension
        db_app = None
        db_found = True

        try:
            db_app = TethysModel.objects.get(package=item_name)
        except TethysModel.DoesNotExist:
            db_found = False

        if not module_found and not db_found:
            warnings.warn('WARNING: {0} with name "{1}" cannot be uninstalled, because it is not installed or'
                          ' not an {0}.'.format(app_or_extension, item_name))
            exit(0)

        # Confirm
        item_with_prefix = '{0}-{1}'.format(PREFIX, item_name)

        valid_inputs = ('y', 'n', 'yes', 'no')
        no_inputs = ('n', 'no')

        if not options['is_forced']:
            overwrite_input = input(
                'Are you sure you want to uninstall "{0}"? (y/n): '.format(item_with_prefix)).lower()

            while overwrite_input not in valid_inputs:
                overwrite_input = input('Invalid option. Are you sure you want to '
                                        'uninstall "{0}"? (y/n): '.format(item_with_prefix)).lower()

            if overwrite_input in no_inputs:
                self.stdout.write('Uninstall cancelled by user.')
                exit(0)

        # Remove app from database
        if db_found and db_app:
            db_app.delete()

            # Get the TethysApp content type
            app_content_type = ContentType.objects.get(
                app_label='tethys_apps',
                model='tethysapp' if not options['is_extension'] else 'tethysextension'
            )

            # Remove any permissions associated to the app/extension
            db_app_permissions = Permission.objects. \
                filter(content_type=app_content_type). \
                filter(name__icontains=f'{db_app.package} | '). \
                all()

            for db_app_permission in db_app_permissions:
                db_app_permission.delete()

            # Remove any groups associated to the app/extension
            db_app_groups = Group.objects. \
                filter(name__icontains=f'{db_app.package}:'). \
                all()

            for db_app_group in db_app_groups:
                db_app_group.delete()

        # Uninstall using pip
        process = ['pip', 'uninstall', '-y', '{0}-{1}'.format(PREFIX, item_name)]

        try:
            subprocess.Popen(process, stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
        except KeyboardInterrupt:
            pass

        # Remove the namespace package file if applicable.
        for site_package in site.getsitepackages():
            try:
                os.remove(os.path.join(site_package, "{}-{}-nspkg.pth".format(PREFIX, item_name.replace('_', '-'))))
            except Exception:
                continue

        self.stdout.write('{} "{}" successfully uninstalled.'.format(app_or_extension, item_with_prefix))
