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

def authenticate(donation_type='Recurrent'):
    '''Authenticate and create a session on CMCIC website.'''
    cm_user, cm_pass, _ = credentials(donation_type)
    payload = {'_cm_user': cm_user, '_cm_pwd': cm_pass}
    r = s.post('https://www.cmcicpaiement.fr/fr/identification/default.cgi', data=payload)


def credentials(donation_type='Recurrent'):
    '''Return credentials from config file.'''
    cm_user = config.get(donation_type, 'cm_user')
    cm_pass = config.get(donation_type, 'cm_pass')
    tpe_id  = config.get(donation_type, 'tpe_id')
    
    if not cm_user:
        print('ERROR: cm_user not defined in config file')
        exit()
        
    if not cm_pass:
        print('ERROR: cm_pass not defined in config file')
        exit()
        
    if not tpe_id:
        print('ERROR: tpe_id not defined in config file')
        exit()

    return cm_user, cm_pass, tpe_id


def now():
    '''Return current date.'''
    return datetime.now()
    
    
def begin_date():
    '''Return the date one month ago formatted.'''
    return (now() + relativedelta(months=-1)).strftime('%d/%m/%Y')
    
    
def end_date():
    ''' Return the date in one month formatted.'''
    return (now() + relativedelta(months=+1)).strftime('%d/%m/%Y')
    
    
def card_is_expired(reference, date_donation, tpe_id):
    '''Return True if donation card expires next month.'''
    url  = 'https://www.cmcicpaiement.fr/fr/client/Paiement/DetailPaiement.aspx?reference={0}&tpe={1}&date={2}&tpe_id={1}:PR'.format(reference, tpe_id, date_donation)
    html = bs(s.get(url).content)

    try:
        fiche = html.find('table', {'class': 'fiche'})
        line  = fiche.findAll('tr')[8].text
        
        expiration_date = line.split('client')[1]
        if expiration_date == '&nbsp;':
            return False
        
        current_month = now().strftime('%m/%y')
        next_month    = (now() + relativedelta(months=+1)).strftime('%m/%y')
        
        return expiration_date if expiration_date in (current_month, next_month) else False
    except AttributError:
        return False

    
def get_donations(tpe_id, donation_type='Recurrent', full=False):
    '''Get donation information from CMCIC website.'''
    authenticate(donation_type)

    url = 'https://www.cmcicpaiement.fr/fr/client/Paiement/Paiement_RechercheAvancee.aspx?__VIEWSTATE=/wEPDwULLTE1NDI1MDc3MTVkZA==&tpe_id={0}:PR&SelectionCritere=Achat&Date_Debut={1}&Date_Fin={2}&NumeroTpe={0}:PR&export=XML'.format(tpe_id, begin_date(), end_date())
    
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
            
            if str(amount) != '-21474836.48': # ugly hack to fix some overflow issue
                total_amount += int(amount)
            total_donators += 1
            
            if full and donation_type == 'Recurrent':
                if state.encode('utf-8') != 'Payé':
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

if __name__ == '__main__':    
    parser = argparse.ArgumentParser(
        description='Donation stats from CMCIC',
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
        help='Show details on expired cards/unpaid donations'
    )
    parser.add_argument(
        '-o',
        dest='output',
        type=argparse.FileType('wt'),
        help='Output file'
    )
    
    args = parser.parse_args()
    full = args.full
    
    cm_user, cm_pass, tpe_id = credentials()
    
    rec_amount, rec_nb, unpaid, expired = get_donations(tpe_id, 'Recurrent', full)
    ponc_amount, ponc_nb, _, _ = get_donations(tpe_id, 'Ponctuel', full)
    
    if args.output:
        sys.stdout = args.output
    
    if args.export == 'text':
        print('-----------------------------------------------------------------------------')
        print('# Du %s au %s                                                                ' % (begin_date(), end_date()))
        print('-----------------------------------------------------------------------------')
        print('# Total de dons ponctuels                                  |    %10s €       ' % ponc_amount)
        print('# Nombre de donateurs ponctuels                            |    %10s         ' % ponc_nb)
        print('-----------------------------------------------------------------------------')
        print('# Total de dons récurrents                                 |    %10s €       ' % rec_amount)
        print('# Nombre de donateurs récurrents                           |    %10s         ' % rec_nb)
        print('# Nombre de cartes expirées                                |    %10s         ' % len(expired))
        print('# Nombre de dons qui requièrent une action                 |    %10s         ' % len(unpaid))
        print('-----------------------------------------------------------------------------')
        if full:
            print('### Références des dons qui requièrent une action ###')
            pprint(unpaid)
            print('-----------------------------------------------------------------------------')
            print('### Références des cartes expirées ###')
            pprint(expired)
            print('-----------------------------------------------------------------------------')
    elif args.export == 'json':
        print(
            json.dumps({
                'date_debut': begin_date(),
                'date_fin': end_date(),
                'total_ponctuels': ponc_amount,
                'nb_ponctuels': ponc_nb,
                'total_recurrents': rec_amount,
                'nb_reccurents': rec_nb,
                'nb_expired': len(expired),
                'nb_action': len(unpaid),
                'unpaid': unpaid,
                'expired': expired,
            })
        )
        