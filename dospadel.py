# -*- coding: utf-8 -*-
import datetime
import cgi
import datetime
import urllib
import urllib2
import webapp2
import jinja2

import os

import paypal

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import images                         #tratamiento de imagenes
from google.appengine.ext import blobstore                      #subida de archivos
from google.appengine.ext.webapp import blobstore_handlers


class Product(db.Model):
    """ Models an individual product """
    nm = db.StringProperty()
    desc = db.StringProperty()
    tags = db.StringProperty()
    image = blobstore.BlobReferenceProperty()

class Reserve(db.Model):
    """ Models an individual reserve"""
    product = db.ReferenceProperty(Product,
                                   collection_name='reserves')
    userid = db.StringProperty()
    dt = db.DateTimeProperty()
    paykey = db.StringProperty() #paypal paykey
    status = db.StringProperty() #payment status
    created = db.DateTimeProperty(auto_now=True) #hora y fecha de creación de la reserva
 

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_text = 'logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_text = 'login'
        

        #busqueda de productos
        founded = []
        searched=self.request.get('searched').split(' ',10)
        for word in searched:
            products = Product.all()                                    #consulta productos en bd
            for product in products:
                tags = product.tags.split(',',20)
                for tag in tags:
                    if tag==word:
                        founded.append(product)                         #agrega producto a la lista
                        break
        
        #variables de la plantilla
        template_values = {
            'url': url,
            'url_text': url_text,
            'nickname': user,
            'founded': founded,
        }
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))

class ProductPage(webapp2.RequestHandler):
    """Pagina de cada producto"""
    def get(self):
        """formulario para nuevo producto"""
        upload_url = blobstore.create_upload_url('/upload')      #upload URL for the product image

        template_values = {
            'upload_url': upload_url,
        }
        template = jinja_environment.get_template('product.html')
        self.response.out.write(template.render(template_values))

class UploadProductImage(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('img')
        blob_info = upload_files[0]
        
                                      
        #product=Product()
        ##kind p
        p=Product(key_name=self.request.get('nm'))
        ##properties
        p.nm=self.request.get('nm')
        p.desc=self.request.get('desc')
        p.tags=self.request.get('tags')
        p.image=blob_info.key()
        p.put()
        self.redirect(str('product/'+p.nm))    

class ReservePage(webapp2.RequestHandler):
    """Formalizar reservas de los productos"""
    def get(self,productnm):
        k=db.Key.from_path('Product',productnm)
        product=db.get(k)                                           #ejemplo de consulta por key a la bd

        template_values={
            'product': product,
        }
        template = jinja_environment.get_template('reserve.html')
        self.response.out.write(template.render(template_values))
  
    def post(self,productnm):
        k=db.Key.from_path('Product',productnm)
        product=db.get(k)


        date=self.request.get('date')                               #fecha de la reserva
        time=self.request.get('time')                               #hora  "  "  "
        hours=self.request.get('hours')                             
   
        d=date.split('-',3)
        t=time.split(':',2)
        dt=datetime.datetime(int(d[0]),int(d[1]),int(d[2]),int(t[0]),int(t[1]))

        #falta controlar que las reservas no se solapen
        pp=paypal.Paypal("franje_1356296325_biz_api1.yahoo.es","1356296345",
                         self.request.remote_addr,"AcHhwt4WsEqB3tcpSOplSMzcxiIuAMMH4ZiPLtmz1fASuBhmHQEeWAQX")
        paykey=pp.pay("http://dospadel.appspot.com/reserves","es_ES","EUR","franje18@yahoo.es",10.00,
                      "http://dospadel.appspot.com",
                      "http://dospadel.appspot.com/transactions")
            
        res=Reserve(key_name=paykey)
        res.product=product
        res.paykey=paykey
        res.status="unknow"
        res.userid=users.get_current_user().user_id()
        res.dt=dt
        res.put()
        
        self.redirect('https://www.sandbox.paypal.com/webscr?cmd=_ap-payment&'+urllib.urlencode({'paykey':paykey}) )


class MyReservesPage(webapp2.RequestHandler):
    """Detalle de reservas de cada usuario"""
    def get(self):
        reserves = db.GqlQuery("SELECT *  "
                               "FROM Reserve "
                               "WHERE userid = :1 "
                               "ORDER BY created DESC LIMIT 10",
                               users.get_current_user().user_id())

        template_values={
            'reserves' : reserves,
            'user' : users.get_current_user(),
        }
        template = jinja_environment.get_template('myreserves.html')
        self.response.out.write(template.render(template_values))

class ReserveDetailPage(webapp2.RequestHandler):
    """Detalle de una reserva concreta."""
    def get(self,paykey):
        k=db.Key.from_path('Reserve',paykey)
        reserve=db.get(k)

        template_values={
            'reserve' : reserve,
        }
        template = jinja_environment.get_template('reservedetail.html')
        self.response.out.write(template.render(template_values))

class ProductImage(webapp2.RequestHandler):
    """Muestra la imagen correspondiente al producto"""
    def get(self,productnm):
        k = db.Key.from_path('Product',productnm)
        product = db.get(k)

        blob_info = product.image
        if blob_info:
            img = images.Image(blob_key=blob_info.key())
            img.resize(width=100,height=100)
            img=img.execute_transforms(output_encoding=images.JPEG)
            self.response.headers['Content-Type']='image/jpeg'
            self.response.out.write(img)
            return
        self.error(404)


class Transactions(webapp2.RequestHandler):
    """Recibe mensajes IPN de la API de paypal y agrega informacioon a Reserve"""
    def get(self):
        self.request.GET.copy()
        
    def post(self):
        ##verificar que el mensaje procede de paypal
        verify_request=urllib2.Request("https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_notify-validate&",urllib.urlencode(self.request.POST.copy()))
        verify_response = urllib2.urlopen(verify_request)
        if verify_response.code != 200:
            self.error='Paypal response code was %i' % verify_response
            return
        raw_response=verify_response.read()
        if raw_response != 'VERIFIED':
            self.error='Paypal response was %s' % raw_response
            return
        
        paykey=self.request.get('pay_key')
        k = db.Key.from_path('Reserve',paykey)
        reserve=db.get(k)
        reserve.status=self.request.get('status')
        reserve.put()


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/product/(.*)/img', ProductImage),
                               ('/new_product', ProductPage),
                               ('/reserves',MyReservesPage),
                               ('/upload', UploadProductImage),
                               (r'/product/(.*)',ReservePage),
                               (r'/reserves/(.*)',ReserveDetailPage),
                               ('/transactions',Transactions),
                              ],
                              debug=True)
