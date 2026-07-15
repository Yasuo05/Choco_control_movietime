from django import forms
from .models import Caja, Cierre, Jornada, Producto


class DateInput(forms.DateInput):
    input_type = 'date'


class JornadaForm(forms.ModelForm):
    class Meta:
        model = Jornada
        fields = ['fecha', 'caja', 'observaciones']
        widgets = {'fecha': DateInput(), 'observaciones': forms.Textarea(attrs={'rows': 3})}


class CajaForm(forms.ModelForm):
    class Meta:
        model = Caja
        fields = ['nombre', 'tipo', 'activa']


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'categoria', 'codigo_vaso', 'codigo_botella', 'descripcion_vaso',
            'descripcion_botella', 'convertible', 'confirmado', 'notas', 'activo',
        ]
        widgets = {'notas': forms.Textarea(attrs={'rows': 3})}


class CierreForm(forms.ModelForm):
    class Meta:
        model = Cierre
        fields = ['numero', 'modalidad_periodo', 'motivo_cambio', 'imagen', 'productos_convertir']
        widgets = {
            'productos_convertir': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'modalidad_periodo': 'Presentación entregada en este periodo',
            'productos_convertir': 'Productos específicos que pasan a botella',
        }
        help_texts = {
            'numero': 'El cierre 1 cubre desde la apertura; el cierre 2 cubre las ventas nuevas desde el cierre 1, etc.',
            'productos_convertir': 'Déjelo vacío si todos los combos convertibles del periodo fueron entregados con botella.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['productos_convertir'].queryset = Producto.objects.filter(convertible=True, confirmado=True, activo=True).order_by('nombre')


class RevisionDetallesForm(forms.Form):
    detalles_texto = forms.CharField(
        label='Códigos y cantidades acumuladas del cierre',
        widget=forms.Textarea(attrs={
            'rows': 14,
            'placeholder': '3088,10\n2518,4\n2485,2',
            'class': 'monospace',
        }),
        help_text='Escriba una línea por producto con el formato CODIGO,CANTIDAD. La cantidad debe ser la acumulada que aparece en la boleta.',
    )
