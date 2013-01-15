# -*- coding: utf-8 -*-
import datetime
import cgi
import datetime
import urllib
import webapp2
import jinja2

import os

import paypal

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

from google.appengine.ext import db
from google.appengine.api import users

class Journey(db.Model):
    """ contiene horas de la jornada laboral """
    hr = db.IntegerProperty()

class Holiday(db.Model):
    """ contiene dias no laborables """
    hld = db.DateProperty()

class Product(db.Model):
    """ Models an individual product """
    nm = db.StringProperty()
    desc = db.StringProperty()
    tags = db.StringProperty()

class Reserve(db.Model):
    product = db.ReferenceProperty(Product,
                                   collection_name='reserves')
    userid = db.StringProperty()
    dt = db.DateTimeProperty()
    paykey = db.StringProperty() #paypal paykey
    status = db.StringProperty() #payment status

class Administrator(db.Model):
    userid = db.StringProperty()

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_text = 'logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_text = 'login'
        
        founded = []  #productos encontrados 
        searched=self.request.get('searched').split(' ',10)
        for word in searched:
            products = Product.all()
            for product in products:
                tags = product.tags.split(',',20)
                for tag in tags:
                    if tag==word:
                        founded.append(product)
                        break
        

        template_values = {
            'url': url,
            'url_text': url_text,
            'nickname': user,
            'founded': founded,
        }
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))

class ProductPage(webapp2.RequestHandler):
    def get(self):
        products=Product.all()

        template_values = {
            'products': products,
        }
        template = jinja_environment.get_template('product.html')
        self.response.out.write(template.render(template_values))

    def post(self):
        product=Product()
        
        #kind p
        p=Product(key_name=self.request.get('nm'))
        #properties
        p.nm=self.request.get('nm')
        p.desc=self.request.get('desc')
        p.tags=self.request.get('tags')
        p.put()
            
        self.redirect('product?'+urllib.urlencode({'nm':product.nm}))    

class ReservePage(webapp2.RequestHandler):
    def get(self,productnm):
        k=db.Key.from_path('Product',productnm)
        product=db.get(k)

        template_values={
            'product': product,
        }
        template = jinja_environment.get_template('reserve.html')
        self.response.out.write(template.render(template_values))
  
    def post(self,productnm):
        date=self.request.get('date')
        time=self.request.get('time')
        self.request.get('hours')
        ##comprueba que la fechahora es correcta y está disponible
        ##si es asi
        d=date.split('-',3)
        t=time.split(':',2)
        reserve_date=datetime.date(int(d[0]),int(d[1]),int(d[2]))
        reserve_time=datetime.time(int(t[0]),int(t[1]))

        r = Reserve.all()
        r.filter('date=',reserve_date).filter('time=',reserve_time)
        if r.count()>0:
            self.redirect('product/'+productnm)
        else:
            #self.redirect('product?'+urllib.urlencode({'ip':self.request.remote_addr}))
            pp=paypal.Paypal("franje_1356296325_biz_api1.yahoo.es","1356296345",self.request.remote_addr,"AcHhwt4WsEqB3tcpSOplSMzcxiIuAMMH4ZiPLtmz1fASuBhmHQEeWAQX")
            out=pp.pay("http://dospadel.appspot.com","es_ES","EUR","franje18@yahoo.es",10.00,"http://dospadel.appspot.com","http://dospadel.appspot.com/reserve")
            #self.redirect('https://www.paypal.com/webapps/adaptivepayment/flow/pay?'+urllib.urlencode({'paykey':out}))
            self.redirect('https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_ap-payment&paykey=%s' % out)

class IPNHandler(webapp2.RequestHandler):
    def post(self):
        #leer informacion recibida por POST y reenviar a paypal
        verify_request = urllib2.Request('https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_notify-validate',
                                         self.request.copy)
        verify_response = urllib2.urlopen(verify_request)
        raw_response=verify_response.content()
        
        self.response.out.write(raw_response)
        
        

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/product', ProductPage),
                               (r'/product/(.*)',ReservePage),
                               ('/reserve', IPNHandler)],
                              debug=True)
