# -*- coding: utf-8 -*-
import datetime
import cgi
import datetime
import urllib
import urllib2
import webapp2
import jinja2
import json
import os
import paypal
import logging


jinja_environment = jinja2.Environment(
        loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import images                         #tratamiento de imagenes
from google.appengine.ext import blobstore                      #subida de archivos
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import urlfetch
from google.appengine.api import mail

#######################################################################################################
#  MODELO DE DATOS

class Product(db.Model):
    """ Models an individual product """
    nm = db.StringProperty()
    desc = db.StringProperty()
    tags = db.StringProperty()
    price = db.FloatProperty()
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
    hide = db.BooleanProperty()  #oculta la reserva

##dias no laborables en los que no se permiten reservas
class Holiday(db.Model):
    """ Models an individual holiday """
    day = db.DateProperty()
    comment = db.StringProperty()

##jornada laboral
class Journey(db.Model):
    hour = db.IntegerProperty()

#
########################################################################################################
    
class MainPage(webapp2.RequestHandler):
    """Manejo de la pagina principal"""
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
            'user': user,
            'founded': founded,
            'admin' : users.is_current_user_admin(),
        }
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))

class ProductPage(webapp2.RequestHandler):
    """Pagina insertar nuevo producto"""
    def get(self):
        """formulario para nuevo producto"""

        ## login
        user = users.get_current_user()
        url = users.create_logout_url(self.request.uri)
        url_text = 'logout'
        
        upload_url = blobstore.create_upload_url('/upload')      #upload URL for the product image

        template_values = {
            'upload_url': upload_url,
            'url': url,
            'url_text': url_text,
            'user': user,
            'admin' : users.is_current_user_admin(),
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
        p.price=float(self.request.get('price'))
        p.put()
        self.redirect(str('product/'+p.nm))    

class Check(webapp2.RequestHandler):
    """Comprueba disponibilidad de una reserva"""
    def post(self):
        form_date=self.request.get('date')
        form_time=self.request.get('time')
        form_name=self.request.get('name')  #nombre del producto

        #if form_date or form_time == '':
        #    self.response.out.write(1)

        d=form_date.split('-',3)
        t=form_time.split(':',3)
        dt=datetime.datetime(int(d[2]),int(d[1]),int(d[0]),int(t[0]))

        #TODO tener en cuenta dias festivos
        #hay que reservar con 12 horas de antelacion
        if dt < (datetime.datetime.now()+datetime.timedelta(hours=12)):
            logging.info("intento de reserva en el pasado o con poca antelacion")
            self.response.out.write(1)

        k = db.Key.from_path('Product', form_name)
        product=db.get(k)
  
        reserves = db.GqlQuery("SELECT *  "
                               "FROM Reserve "
                               "WHERE dt = :1 AND product = :2 AND status = :3 ",
                               dt,product,'Completed')
        logging.info('check devuelve '+str(reserves.count()))
        self.response.out.write(reserves.count())

class ReservePage(webapp2.RequestHandler):
    """Maneja las reservas de los productos"""
    def get(self,productnm):


        ## login
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_text = 'logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_text = 'login'



        k=db.Key.from_path('Product',productnm)
        product=db.get(k)                                           #ejemplo de consulta por key a la bd

        journey=Journey.all()

        template_values={
            'product': product,
            'user': user,
            'url_text': url_text,
            'url': url,
            'journey': journey,
            'admin' : users.is_current_user_admin(),
        }
        template = jinja_environment.get_template('reserve.html')
        self.response.out.write(template.render(template_values))
  
    def post(self,productnm):

        date=self.request.get('date')                               #fecha de la reserva
        time=self.request.get('time')                               #hora  "  "  "


        ##compruebo que no existe ya una reserva a esa hora y ese dia
        form_fields = {
            "name":productnm,
            "date":date,
            "time":time
        }

        # consulta a /check que dice si la reserva esta libre o no        
        form_data = urllib.urlencode(form_fields)
        result = urlfetch.fetch(url='http://dospadel.appspot.com/check',
                                payload=form_data,
                                method=urlfetch.POST,
                                headers={'Content-Type':'application/x-www-form-urlencoded'})
        
        if result.status_code == 200:
            if int(result.content) == 0:
                d=date.split('-',3)
                t=time.split(':',2)
                dt=datetime.datetime(int(d[2]),int(d[1]),int(d[0]),int(t[0]),int(t[1]))  #formato fecha mm/dd/yyyy
                k=db.Key.from_path('Product',productnm)
                product=db.get(k)
                
                p=paypal.Pay("franje_1356296325_biz_api1.yahoo.es","1356296345",
                                 self.request.remote_addr,"AcHhwt4WsEqB3tcpSOplSMzcxiIuAMMH4ZiPLtmz1fASuBhmHQEeWAQX")
                paykey=p.pay("http://dospadel.appspot.com/reserves","es_ES","EUR","franje_1356296325_biz@yahoo.es",product.price,
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
            else:
                logging.info('intento de registrar una reserva erronea')

class MyReservesPage(webapp2.RequestHandler):
    """Maneja el detalle de reservas de cada usuario"""
    def get(self):

        ## login
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_text = 'logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_text = 'login'

        reserves = db.GqlQuery("SELECT *  "
                               "FROM Reserve "
                               "WHERE userid = :1 and status = :2 "
                               "ORDER BY created DESC LIMIT 10",
                               users.get_current_user().user_id(),
                               "Completed")
        #puede ser más económico hacer lo anterior con filte en lugar de tres consultas

        template_values={
            'reserves': reserves,
            'user' : users.get_current_user(),
            'url' : url,
            'url_text' : url_text,
            'admin' : users.is_current_user_admin(),
        }
        template = jinja_environment.get_template('myreserves.html')
        self.response.out.write(template.render(template_values))

class ReserveDetailPage(webapp2.RequestHandler):
    """Detalle de una reserva concreta."""
    def get(self,paykey):
        ## login
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_text = 'logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_text = 'login'

        k=db.Key.from_path('Reserve',paykey)
        reserve=db.get(k)

        template_values={
            'reserve': reserve,
            'user' : users.get_current_user(),
            'url' : url,
            'url_text' : url_text,
            'admin' : users.is_current_user_admin(),
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
        pass
        
    def post(self):
        """Procesa mensajes IPN  de paypal"""

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
        
        #logging.info(self.request.POST.copy())

        reserve=db.get(k)
        reserve.status=self.request.get('transaction[0].status_for_sender_txn')

        #obtengo datos del usuario para enviar mail.
        user = users.User(reserve.userid)

        ##email informativo
        message = mail.EmailMessage(sender="dospadel <franciscojesusjimenez@gmail.com>",
                                    subject="Reserva completada")
        message.to = user.nickname()+"<"+user.email()+">"
        message.body = """
            Reserva confirmada para el usuario %s para la fecha %s
            a las %s. El codigo de la reserva es %s. Para detalles y cancelaciones (antes 
            de transcurridas 2 horas desde que se efectuo la reserva) puede acceder en la
            siguiente direccion http://dospadel.appspot.com/reserves/%s

            Atentamente
            DOSPADEL.com

        """ % (user.email(), reserve.dt.date(), reserve.dt.time(), reserve.paykey, reserve.paykey)

        reserve.put()
        try:
            message.send()  #envio email informando al usuario de la transaccion
        except (BadRequestError, InvalidSenderError,InvalidEmailError):
            logging.info("error al enviar el mail")
class CancelReserve(webapp2.RequestHandler):
    """Cancela una reserva y devuelve el dinero"""
    def get(self):
        pass

    def post(self):
        """ Comprueba que la reserva se puede cancelar, y si es así
            cancela """


        #TODO Requisitos para poder cancelar
        #     No haber transcurrido mas de 12 horas desde que se reservó
        #     
        p=paypal.Refund("franje_1356296325_biz_api1.yahoo.es","1356296345",
                         self.request.remote_addr,"AcHhwt4WsEqB3tcpSOplSMzcxiIuAMMH4ZiPLtmz1fASuBhmHQEeWAQX")
        
        p.refund(self.request.get('paykey'))
        
        
        self.redirect("/reserves/")

class AllProductsPage(webapp2.RequestHandler):
    """Lista todos los productos disponibles"""
    def get(self):
        ## login
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_text = 'logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_text = 'login'

        products = Product.all()
        template_values={
            'products' : products,
            'user' : user,
            'url_text' : url_text,
            'url' : url,
            'admin' : users.is_current_user_admin(),
        }
        template = jinja_environment.get_template('all_products.html')
        self.response.out.write(template.render(template_values))

class AdminPage(webapp2.RequestHandler):
    """configuracion para el administrador"""
    def get(self):
        ## login
        user = users.get_current_user()
        url = users.create_logout_url(self.request.uri)
        url_text = 'logout'
        
        template_values={
            'user' : users.get_current_user(),
            'url' : url,
            'url_text' : url_text,
            'admin' : users.is_current_user_admin(),
        }
        template = jinja_environment.get_template('admin.html')
        self.response.out.write(template.render(template_values))
    def post(self):
        o = self.request.get('option')
        if o == 'jl':
            #agregar hora a jornada laboral
            jl=Journey()
            jl.hour=int(self.request.get('hr'))
            jl.put()
            return
        if o == 'df':
            #agregar dia festivo a jornada laboral
            dt_string=self.request.get('dt')
            d=dt_string.split('-',3)
            
            df=Holiday()
            df.day=datetime.date(int(d[0]),int(d[1]),int(d[2]))
            df.comment=self.request.get('comment')
            df.put()
            return
        self.redirect('/admin')

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/product/(.*)/img', ProductImage),
                               ('/new_product', ProductPage),
                               ('/reserves',MyReservesPage),
                               ('/upload', UploadProductImage),
                               (r'/product/(.*)',ReservePage),
                               (r'/reserves/(.*)',ReserveDetailPage),
                               ('/transactions',Transactions),
                               ('/check', Check),
                               ('/products',AllProductsPage),
                               ('/admin',AdminPage),
                               ('/cancel_reserve',CancelReserve),
                              ],
                              debug=True)
