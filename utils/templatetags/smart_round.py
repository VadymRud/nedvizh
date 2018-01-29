from django.template import Library
import math

register = Library()

@register.filter()
def smart_round(number):
    if number > 100:
        pow = math.pow(10, len(str(number))-2)
        number = int(math.ceil( number / pow ) * pow)
    return number

