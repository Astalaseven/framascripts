# -*- coding: utf-8 -*-
##############################################################################
#
#   Framasoft
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public Licence as
#   published by the Free Software Foundation, either version 2 of the
#   Licence, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without event the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU General Public Licence for more details.
#
#   You should have received a copy of the GNU General Public Licence
#   along with this program. If not, see <http://www.gnu.org/licences/>.
#
#   @author: Quentin THEURET <quentin.theuret@framasoft.org>
#
##############################################################################

import ConfigParser
import mechanize
import cookielib
import json
import argparse

from mx.DateTime import RelativeDateTime
from mx.DateTime import now
from BeautifulSoup import BeautifulSoup

from lxml import etree


last_month = now() + RelativeDateTime(months=-1, days=1)
next_month = now() + RelativeDateTime(months=1, day=1)
DATE_FIN = '%s/%s/%s' % (now().day, str(now().month).rjust(2, '0'), now().year)
DATE_DEBUT = '%s/%s/%s' % (last_month.day, str(last_month.month).rjust(2, '0'), last_month.year)

def don_is_expired(browser, reference, date_don, tpe_id):
    '''
    Retourne True si la carte qui a servi à faire le don expire le mois prochain
    '''
    url = 'https://www.cmcicpaiement.fr/fr/client/Paiement/DetailPaiement.aspx?reference=%(reference)s&tpe=%(tpe_id)s&date=%(date_don)s&tpe_id=%(tpe_id)s:PR' % {
        'date_don': date_don,
        'tpe_id': tpe_id,
        'reference': reference,
    }
    r = browser.open(url)
    html = r.read()

    parsed_html = BeautifulSoup(html)

    fiche = parsed_html.body.find('table', attrs={'class': 'fiche'}).text
    try:
        expiration = fiche.split('expiration de la carte bancaire du client')[1][:5]
        next_month_exp = next_month.strftime('%m/%y')
        current_month_exp = now().strftime('%m/%y')
        if expiration in (next_month_exp, current_month_exp):
            return expiration
    except IndexError:
        return False

    return False

def get_dons(type_don='Recurrent', full=None):
    assert type_don in ('Recurrent', 'Ponctuel'), "Le type de don doit être 'Récurrent' ou 'Ponctuel'"
    # Config
    config = ConfigParser.ConfigParser()
    config.readfp(open('./cmcic.cfg'))

    # Browser
    br = mechanize.Browser()

    # Cookie Jar
    cj = cookielib.LWPCookieJar()
    br.set_cookiejar(cj)

    # Browser options
    br.set_handle_equiv(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)

    # Follows refresh 0 but not hangs on refresh > 0
    br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

    # User-Agent (this is cheating, ok ?)
    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]


    r = br.open('https://www.cmcicpaiement.fr/fr/identification/identification.html')
    html = r.read()

    br.select_form(name='bloc_ident')
    br.form['_cm_user'] = config.get(type_don, 'cm_user')
    br.form['_cm_pwd'] = config.get(type_don, 'cm_pwd')

    if not br.form['_cm_user']:
        print 'Pas d\'utilisateur rempli dans le fichier cmcic.cfg !'
        exit(1)
    if not br.form['_cm_pwd']:
        print 'Pas de mot de passe rempli dans le fichier cmcic.cfg !'
        exit(1)

    br.submit()


    TPE_ID = config.get(type_don, 'tpe_id')
    if not TPE_ID:
        print 'Pas numéro de TPE rempli dans le fichier cmcic.cfg !'
        exit(1)

    url = 'https://www.cmcicpaiement.fr/fr/client/Paiement/Paiement_RechercheAvancee.aspx?__EVENTTARGET=&__EVENTARGUMENT=&__VIEWSTATE=/wEPDwULLTE1NDI1MDc3MTVkZA==&tpe_id=%s:PR&commande_action=&commande_tri=commande_date+de+paiement&commande_sens=1&commande_page=1&SelectionCritere=Achat&Date_Debut=%s&Date_Fin=%s&Reference=&Paye=on&Paye.p=&Annule.p=&Refuse.p=&PartiellementPaye=on&PartiellementPaye.p=&Enregistre=on&Enregistre.p=&CarteNonSaisie.p=&EnCours=on&EnCours.p=&Montant_Min=&Montant_Max=&Currency=EUR&SelectionAffichage=Ecran&AdresseMail=&Btn.Find.x=61&Btn.Find.y=8&NumeroTpe=%s:PR&export=XML' % (TPE_ID, DATE_DEBUT, DATE_FIN, TPE_ID)
    r = br.open(url)
    html = r.read()

    total_amount = 0.00
    total_donateur = 0

    root = etree.XML(html)

    unpaid = []
    expired = []

    for element in root.iter("IEnumerableOfXmlCommande"):
        for commande in element.iter("Commande"):
            num_commande = commande.find('Reference').text
            montant = commande.find('Montant').find('Valeur').text
            pay_date = commande.find('DatePaiement').text[:10]
            etat = commande.find('Etat').text
            total_amount += float(montant)
            total_donateur += 1

            if full:
                if type_don == 'Recurrent':
                    if etat.encode('iso-8859-1') != 'Pay\xe9':
                        unpaid.append(num_commande)

                    exp = don_is_expired(br, num_commande, pay_date, TPE_ID)
                    if exp:
                        expired.append((num_commande, exp))

    return total_amount, total_donateur, unpaid, expired

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Arguments Parser')
    parser.add_argument(
        '--export',
        dest='export',
        default='stdout',
        help="""
Défini le type d\'export (choix possibles: stdout*, json)
"""
    )
    parser.add_argument(
        '--full',
        dest='full',
        default=False,
        help="""
Défini si on veut les détails sur les dons expirés/requierent une action (--full=True pour afficher les détails)
"""
    )

    args = parser.parse_args()
    full = None
    full = args.full

    rec_amount, rec_nb, unpaid, expired = get_dons('Recurrent', full=full)
    ponc_amount, ponc_nb, ponc_un, ponc_ex = get_dons('Ponctuel', full=full)

    if args.export == 'stdout':
        print 'Du %s au %s' % (DATE_DEBUT, DATE_FIN)
        print '----------------------------------'
        print '# Total de dons ponctuels : %s' % ponc_amount
        print '# Nombre de donateurs ponctuels : %s' % ponc_nb
        print '----------------------------------'
        print '# Total de dons récurrents : %s' % rec_amount
        print '# Nombre de donateurs récurrents : %s' % rec_nb
        print '# Nombre de carte expirées : %s' % len(expired)
        print '# Nombre de don qui requiert une action : %s' % len(unpaid)
        print '----------------------------------'
        print '### Détails des dons qui requiert une action : ###'
        for un in unpaid:
            print '# Référence : %s' % un
        print '----------------------------------'
        print '### Détails des cartes expirées : ###'
        for ex in expired:
            print '# Référence : %s (expiration : %s)' % (ex[0], ex[1])
    elif args.export == 'json':
        res = {
            'date_debut': DATE_DEBUT,
            'date_fin': DATE_FIN,
            'total_ponctuels': ponc_amount,
            'nb_ponctuels': ponc_nb,
            'total_recurrents': rec_amount,
            'nb_reccurents': rec_nb,
            'nb_expired': len(expired),
            'nb_action': len(unpaid),
            'unpaid': unpaid,
            'expired': [ex for ex in expired],
        }
        print json.dumps(res)
