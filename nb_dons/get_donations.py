#!/usr/bin/env python
# coding: utf-8

import argparse
import ConfigParser
import json
import sys
import xml.etree.ElementTree as et
from datetime import datetime
from os import path

import requests
from BeautifulSoup import BeautifulSoup as bs
from dateutil.relativedelta import relativedelta



s = requests.Session()
config = ConfigParser.ConfigParser()
config.read(path.join(path.dirname(path.realpath(__file__)), 'cmcic.cfg'))

donation_types = config.sections() # ['recurrent', 'onetime', ...]


def authenticate(donation_type):
    '''Authenticate and create a session on CMCIC website.'''
    url              = 'https://www.cmcicpaiement.fr/fr/identification/default.cgi'
    cm_user, cm_pass = credentials(donation_type)
    payload          = {'_cm_user': cm_user, '_cm_pwd': cm_pass}
    return s.post(url, data=payload).status_code == 200


def tpe_id(donation_type):
    '''Return tpe_id from config file.'''
    if donation_type not in donation_types:
        print('ERROR: unknown donation type')
        exit()

    tpe_id = config.get(donation_type, 'tpe_id')

    if not tpe_id:
        print('ERROR: tpe_id not defined in config file')
        exit()

    return tpe_id


def credentials(donation_type):
    '''Return credentials from config file.'''
    if donation_type not in donation_types:
        print('ERROR: unknown donation type')
        exit()

    cm_user = config.get(donation_type, 'cm_user')
    cm_pass = config.get(donation_type, 'cm_pass')

    if not cm_user:
        print('ERROR: cm_user not defined in config file')
        exit()

    if not cm_pass:
        print('ERROR: cm_pass not defined in config file')
        exit()

    return cm_user, cm_pass


def now():
    '''Return current date.'''
    return datetime.now()


def begin_date(format='%d/%m/%Y'):
    '''Return the date one month ago formatted.'''
    return (now() + relativedelta(months=-1, day=1)).strftime(format)


def end_date(format='%d/%m/%Y'):
    ''' Return the date in one month formatted.'''
    return (now() + relativedelta(months=+1, day=1)).strftime(format)


def card_is_expired(reference, date_donation, tpe_id):
    '''Return True if donation card expires next month.'''
    url  = 'https://www.cmcicpaiement.fr/fr/client/Paiement/DetailPaiement.aspx?' \
    'reference={0}&tpe={1}&date={2}&tpe_id={1}:PR'.format(reference, tpe_id, date_donation)
    html = bs(s.get(url).content)

    try:
        fiche = html.find('table', {'class': 'fiche'})
        line  = fiche.findAll('tr')[8].text

        expiration_date = line.split('client')[1]
        if expiration_date == '&nbsp;':
            return False

        current_month = now().strftime('%m/%y')
        next_month    = end_date('%m/%y')

        return expiration_date if expiration_date in (current_month, next_month) else False
    except AttributError:
        return False


def get_donations(tpe_id, donation_type, full=False):
    '''Get donation information from CMCIC website.'''
    if not authenticate(donation_type):
        print('ERROR: Could not authenticate')
        exit()

    url = 'https://www.cmcicpaiement.fr/fr/client/Paiement/Paiement_RechercheAvancee.aspx?__VIEWSTATE=/wEPDwULLTE1NDI1MDc3MTVkZA==&' \
    'tpe_id={0}:PR&SelectionCritere=Achat&Date_Debut={1}&Date_Fin={2}&NumeroTpe={0}:PR&export=XML'.format(tpe_id, begin_date(), end_date())

    root = et.fromstring(s.get(url).content)

    total_amount   = 0
    total_donators = 0

    unpaid  = []
    expired = []

    for element in root.iter('IEnumerableOfCommandeFormatExport'):
        for order in element.findall('Commande'):

            num_order = order.find('Reference').text
            amount    = order.find('Montant').find('Valeur').text
            pay_date  = order.find('DatePaiement').text[:10]
            state     = order.find('Etat').text

            paid      = state.encode('utf-8') == 'Payé'

            if str(amount) != '-21474836.48': # ugly hack to fix some overflow issue
                if paid:
                    total_amount   += int(amount)
                    total_donators += 1

                if full and donation_type != 'onetime':
                    if not paid:
                        unpaid.append(num_order)

                    exp = card_is_expired(num_order, pay_date, tpe_id)
                    if exp:
                        expired.append(num_order.encode('utf-8'))
                            
    return total_amount, total_donators, unpaid, expired


def pprint(donations, columns=5):
    str = ' '
    cpt = 0
    for cpt, elem in enumerate(donations, 1):
        str += elem + '    '
        if cpt % columns == 0:
            print(str)
            str = ' '
    if cpt % columns != 0:
        print(str)


def text_export(donation_type, amount, nb, unpaid, expired):
    print('# {0}                                                                        '.format(donation_type))
    print('-----------------------------------------------------------------------------')
    print('# Total donations                                        |    {0: >10} €     '.format(amount))
    print('# Number of donations                                    |    {0: >10}       '.format(nb))
    print('-----------------------------------------------------------------------------')
    if expired:
        print('# Expired cards                                          |    {0: >10}'.format(len(expired)))
    if unpaid:
        print('# Unpaid donations                                       |    {0: >10}'.format(len(unpaid)))
    if expired or unpaid:
        print('-----------------------------------------------------------------------------')

    if full:
        if unpaid:
            print('###  Unpaid donation references  ###')
            pprint(unpaid)
            print('-----------------------------------------------------------------------------')
        if expired:
            print('###   Expired card references    ###')
            pprint(expired)
            print('-----------------------------------------------------------------------------')


def exit_handler():
    os.unlink(pidfile)


if __name__ == '__main__':
    import atexit
    import os

    pid     = str(os.getpid())
    pidfile = '/tmp/get_donations.pid'

    if os.path.isfile(pidfile):
        print('{} already exists, exiting'.format(pidfile))
        exit()
    else:
        file(pidfile, 'w').write(pid)
        
    atexit.register(exit_handler)
   
    parser = argparse.ArgumentParser(
        description='Donation statistics from CMCIC',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--export',
        dest='export',
        default='text',
        choices=('text', 'json'),
        help='Define export type'
    )
    parser.add_argument(
        '--full',
        dest='full',
        default=False,
        action='store_true',
        help='Show details on expired cards/unpaid donations (slower)'
    )
    parser.add_argument(
        '-o',
        dest='output',
        type=argparse.FileType('wt'),
        help='Output file'
    )

    args = parser.parse_args()
    full = args.full

    if args.output:
        sys.stdout = args.output

    jsn = {}

    if args.export == 'text':
        print('-----------------------------------------------------------------------------')
        print('# From {} to {}                                                              '.format(begin_date(), end_date()))
        print('-----------------------------------------------------------------------------')

        for donation_type in donation_types:
            amount, nb, unpaid, expired = get_donations(tpe_id(donation_type), donation_type, full)

            text_export(donation_type, amount, nb, unpaid, expired)

    elif args.export == 'json':
        jsn['begin_date'] = begin_date()
        jsn['end_date']   = end_date()

        for donation_type in donation_types:
            amount, nb, unpaid, expired = get_donations(tpe_id(donation_type), donation_type, full)

            jsn[donation_type] = {
                'amount'     : amount,
                'nb'         : nb,
                'nb_unpaid'  : len(unpaid),
                'unpaid'     : unpaid,
                'nb_expired' : len(expired),
                'expired'    : expired
            }

        print(json.dumps(jsn, sort_keys=True, indent=4, separators=(',', ': ')))
