from django import template

register = template.Library()


@register.filter
def iniciales(nombre_completo):
    """'Elizabeth Villanueva' -> 'EV'. Usado en el avatar del navbar
    compartido, que ya no tiene un modelo User del que sacar
    first_name/last_name por separado."""
    if not nombre_completo:
        return ''
    partes = nombre_completo.split()
    return ''.join(parte[0] for parte in partes[:2]).upper()
