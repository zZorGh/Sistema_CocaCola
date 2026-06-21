from django import template

register = template.Library()

@register.filter(name='tiene_rol')
def tiene_rol(user, group_name):
    # Si es el superusuario, tiene acceso a todo
    if user.is_superuser:
        return True
    # Verifica si el usuario pertenece al grupo solicitado
    return user.groups.filter(name=group_name).exists()