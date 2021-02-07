# -*- coding: utf_8 -*-
"""Available Actions."""
import logging
import os

from django.conf import settings
from django.views.decorators.http import require_http_methods

from mobsf.DynamicAnalyzer.views.android.operations import (
    get_package_name,
    invalid_params,
    send_response,
)
from mobsf.DynamicAnalyzer.views.android.environment import (
    Environment,
)
from mobsf.DynamicAnalyzer.views.android.tests_xposed import (
    download_xposed_log,
)
from mobsf.DynamicAnalyzer.tools.webproxy import stop_httptools
from mobsf.MobSF.utils import (
    get_http_tools_url,
    is_md5,
    python_list,
)
from mobsf.StaticAnalyzer.models import StaticAnalyzerAndroid

logger = logging.getLogger(__name__)

# AJAX


@require_http_methods(['POST'])
def activity_tester(request, api=False):
    """Exported & non exported activity Tester."""
    data = {}
    try:
        env = Environment()
        test = request.POST['test']
        md5_hash = request.POST['hash']
        if not is_md5(md5_hash):
            return invalid_params(api)
        app_dir = os.path.join(settings.UPLD_DIR, md5_hash + '/')
        screen_dir = os.path.join(app_dir, 'screenshots-apk/')
        if not os.path.exists(screen_dir):
            os.makedirs(screen_dir)
        static_android_db = StaticAnalyzerAndroid.objects.get(
            MD5=md5_hash)
        package = static_android_db.PACKAGE_NAME
        iden = ''
        if test == 'exported':
            iden = 'Exported '
            logger.info('Exported activity tester')
            activities = python_list(static_android_db.EXPORTED_ACTIVITIES)
        else:
            logger.info('Activity tester')
            activities = python_list(static_android_db.ACTIVITIES)
        logger.info('Fetching %sactivities for %s', iden, package)
        if not activities:
            msg = 'No {}Activites found'.format(iden)
            logger.info(msg)
            data = {'status': 'failed',
                    'message': msg}
            return send_response(data, api)
        act_no = 0
        logger.info('Starting %sActivity Tester...', iden)
        logger.info('%s %sActivities Identified',
                    str(len(activities)), iden)
        for activity in activities:
            act_no += 1
            logger.info(
                'Launching %sActivity - %s. %s',
                iden,
                str(act_no),
                activity)
            if test == 'exported':
                file_iden = 'expact'
            else:
                file_iden = 'act'
            outfile = ('{}{}-{}.png'.format(
                screen_dir,
                file_iden,
                act_no))
            env.launch_n_capture(package, activity, outfile)
        data = {'status': 'ok'}
    except Exception as exp:
        logger.exception('%sActivity tester', iden)
        data = {'status': 'failed', 'message': str(exp)}
    return send_response(data, api)

# AJAX


@require_http_methods(['POST'])
def download_data(request, api=False):
    """Download Application Data from Device."""
    logger.info('Downloading app data')
    data = {}
    try:
        env = Environment()
        md5_hash = request.POST['hash']
        if not is_md5(md5_hash):
            return invalid_params(api)
        package = get_package_name(md5_hash)
        if not package:
            data = {'status': 'failed',
                    'message': 'App details not found in database'}
            return send_response(data, api)
        apk_dir = os.path.join(settings.UPLD_DIR, md5_hash + '/')
        httptools_url = get_http_tools_url(request)
        stop_httptools(httptools_url)
        files_loc = '/data/local/'
        logger.info('Archiving files created by app')
        env.adb_command(['tar', '-cvf', files_loc + package + '.tar',
                         '/data/data/' + package + '/'], True)
        logger.info('Downloading Archive')
        env.adb_command(['pull', files_loc + package + '.tar',
                         apk_dir + package + '.tar'])
        logger.info('Stopping ADB server')
        env.adb_command(['kill-server'])
        data = {'status': 'ok'}
    except Exception as exp:
        logger.exception('Downloading application data')
        data = {'status': 'failed', 'message': str(exp)}
    return send_response(data, api)

# AJAX


@require_http_methods(['POST'])
def collect_logs(request, api=False):
    """Collecting Data and Cleanup."""
    logger.info('Collecting Data and Cleaning Up')
    data = {}
    try:
        env = Environment()
        md5_hash = request.POST['hash']
        if not is_md5(md5_hash):
            return invalid_params(api)
        package = get_package_name(md5_hash)
        if not package:
            data = {'status': 'failed',
                    'message': 'App details not found in database'}
            return send_response(data, api)
        apk_dir = os.path.join(settings.UPLD_DIR, md5_hash + '/')
        lout = os.path.join(apk_dir, 'logcat.txt')
        dout = os.path.join(apk_dir, 'dump.txt')
        logger.info('Downloading logcat logs')
        logcat = env.adb_command(['logcat',
                                  '-d',
                                  package + ':V',
                                  '*:*'])
        with open(lout, 'wb') as flip:
            flip.write(logcat)
        logger.info('Downloading dumpsys logs')
        dumpsys = env.adb_command(['dumpsys'], True)
        with open(dout, 'wb') as flip:
            flip.write(dumpsys)
        if env.get_android_version() < 5:
            download_xposed_log(apk_dir)
        env.adb_command(['am', 'force-stop', package], True)
        logger.info('Stopping app')
        # Unset Global Proxy
        env.unset_global_proxy()
        data = {'status': 'ok'}
    except Exception as exp:
        logger.exception('Data Collection & Clean Up failed')
        data = {'status': 'failed', 'message': str(exp)}
    return send_response(data, api)
