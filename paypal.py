import urllib2
import json
import webapp2


class Paypal(object):
    def __init__(self,userid,password,ip,signature,appid="APP-80W284485P519543T"):
        self._headers={                                #inicializa http headers para la API
            "X-PAYPAL-SECURITY-USERID":userid,
            "X-PAYPAL-SECURITY-PASSWORD":password,
            "X-PAYPAL-SECURITY-SIGNATURE":signature,
            "X-PAYPAL-DEVICE-IPADDRESS": ip,
            "X-PAYPAL-REQUEST-DATA-FORMAT":"JSON",
            "X-PAYPAL-RESPONSE-DATA-FORMAT":"JSON",
            "X-PAYPAL-APPLICATION-ID":appid
        } 


class Pay(Paypal):
    """ Efectuar un pago con paypal """
    def pay(self,returnUrl, errorLanguage, currencyCode, email, amount, cancelUrl, ipn_url=None):
        self._data= {   'currencyCode': 'USD',
                        'returnUrl': returnUrl,
                        'cancelUrl': cancelUrl,
                        'requestEnvelope': { 'errorLanguage': 'en_US' },
        }
        self._data['actionType'] = 'PAY'
        self._data['receiverList'] = { 'receiver': [ { 'email': email, 'amount': '%f' % amount } ] }
        if ipn_url != "none":
            self._data['ipnNotificationUrl']=ipn_url
        
        
        self.raw_request=json.dumps(self._data)
        url_request=urllib2.Request("https://svcs.sandbox.paypal.com/AdaptivePayments/Pay",
                                    self.raw_request,self._headers)
        self.raw_response=urllib2.urlopen(url_request).read()
        self.response = json.loads(self.raw_response)
        return self.response['payKey']


class Refund(Paypal):
    """ Efectuar una devolucion con paypal """
    def refund(self,payKey,ipnUrl="http://dospadel.appspot.com/transactions",errorLanguage='es_ES'):
        """efectua una devolucion a partir del paykey del pago"""
        self._data={'payKey':payKey,}
        self._data['requestEnvelope']= {'errorLanguage':errorLanguage}
        
        self.raw_request = json.dumps(self._data)
        url_request = urllib2.Request("https://svcs.sandbox.paypal.com/AdaptivePayments/Refund",
                                    self.raw_request,
                                    self._headers)
        self.raw_response = urllib2.urlopen(url_request,timeout=60).read()
        self.response = json.loads(self.raw_response)

        return self.response
