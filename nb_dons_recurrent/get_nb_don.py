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

from mx.DateTime import RelativeDateTime
from mx.DateTime import now

from lxml import etree


last_month = now() + RelativeDateTime(months=-1, days=1)
DATE_FIN = '%s/%s/%s' % (now().day, str(now().month).rjust(2, '0'), now().year)
DATE_DEBUT = '%s/%s/%s' % (last_month.day, str(last_month.month).rjust(2, '0'), last_month.year)


def get_dons(type_don='Recurrent'):
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

    br.submit()


    TPE_ID = config.get(type_don, 'tpe_id')

    
    url = 'https://www.cmcicpaiement.fr/fr/client/Paiement/Paiement_RechercheAvancee.aspx?__EVENTTARGET=&__EVENTARGUMENT=&tpe_id=%s:PR&commande_action=&commande_tri=commande_date+de+paiement&commande_sens=1&commande_page=0&SelectionCritere=Achat&Date_Debut=%s&Date_Fin=%s&Reference=&Paye=on&Paye.p=&Annule.p=&Refuse.p=&PartiellementPaye=on&PartiellementPaye.p=&Enregistre.p=&CarteNonSaisie.p=&EnCours=on&EnCours.p=&Montant_Min=&Montant_Max=&Currency=EUR&SelectionAffichage=Ecran&AdresseMail=&Btn.Find.x=19&Btn.Find.y=10&NumeroTpe=%s:PR&export=XML' % (TPE_ID, DATE_DEBUT, DATE_FIN, TPE_ID)
    r = br.open(url)
    html = r.read()

    total_amount = 0.00
    total_donateur = 0

    root = etree.XML(html)
    for element in root.iter("IEnumerableOfXmlCommande"):
        for commande in element.iter("Commande"):
            num_commande = commande.find('Reference').text
            montant = commande.find('Montant').find('Valeur').text
            total_amount += float(montant)
            total_donateur += 1

    return total_amount, total_donateur

if __name__ == '__main__':
    rec_amount, rec_nb = get_dons('Recurrent')
    ponc_amount, ponc_nb = get_dons('Ponctuel')
    print 'Du %s au %s' % (DATE_DEBUT, DATE_FIN)
    print '----------------------------------'
    print '# Total de dons récurrents : %s' % rec_amount
    print '# Nombre de donateurs récurrents : %s' % rec_nb
    print '----------------------------------'
    print '# Total de dons ponctuels : %s' % ponc_amount
    print '# Nombre de donateurs ponctuels : %s' % ponc_nb
