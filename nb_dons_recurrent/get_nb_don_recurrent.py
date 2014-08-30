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

from mx.DateTime import DateTime
from mx.DateTime import RelativeDateTime
from mx.DateTime import now

if __name__ == '__main__':
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
    br.form['_cm_user'] = config.get('CMUT', 'cm_user')
    br.form['_cm_pwd'] = config.get('CMUT', 'cm_pwd')

    br.submit()


    TPE_ID = config.get('CMUT', 'tpe_id')
    last_month = now() + RelativeDateTime(months=-1, days=1)


    DATE_DEBUT = '%s%%2F%s%%2F%s' % (now().day, str(now().month).rjust(2, '0'), now().year)
    DATE_FIN = '%s%%2F%s%%2F%s' % (last_month.day, str(last_month.month).rjust(2, '0'), last_month.year)
    
    url = 'https://www.cmcicpaiement.fr/fr/client/Paiement/Paiement_RechercheAvancee.aspx?__EVENTTARGET=&__EVENTARGUMENT=&tpe_id=%s%%3API&SelectionCritere=Achat&Date_Debut=%s&Date_Fin=%s&Reference=&Paye=on&Paye.p=&Refuse.p=&Enregistre.p=&CarteNonSaisie.p=&EnCours.p=&Montant_Min=&Montant_Max=&Currency=EUR&SelectionAffichage=Ecran&AdresseMail=&Btn.Find.x=65&Btn.Find.y=6&NumeroTpe=%s%%3API&export=XML' % (TPE_ID, DATE_DEBUT, DATE_FIN, TPE_ID)
    r = br.open(url)
    html = r.read()

    root = etree.XML(html)
#    for element in root.iter("ArrayOfCommande"):
#        for commande in element.iter("Commande"):
#            print commande[0].tag == 'Reference':

    exit(0)


    soup = BeautifulSoup(html)

    for commande in soup.find_all('Commande'):
        print commande


    fiche = False
    for table in soup.find_all('table'):
        if 'class' in table.attrs and 'fiche' in table['class']:
            fiche = BeautifulSoup(str(table))
            break

    if fiche:
        rows = fiche.find_all('tr')
        for r in rows:
            th = r.find('th')
            td = r.find('td')
            if th.get_text() in ('Methode de paiement', u'Méthode de paiement'):
                if td.find('div').get_text().strip() == 'Carte bancaire':
                    print 'CMUT'
                else:
                    print td
                    print td.find('div').get_text().strip()
